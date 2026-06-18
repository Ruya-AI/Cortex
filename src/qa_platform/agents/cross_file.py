from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from qa_platform.agents.base import ReviewAgent
from qa_platform.core.finding import (
    Evidence,
    FindingCategory,
    Severity,
    Confidence,
)
from qa_platform.core.finding_factory import FindingFactory
from qa_platform.core.schemas import (
    AgentResult,
    FileGroupReviewContext,
    FileReviewContext,
    MemoryDocument,
    ToolCallRecord,
)

logger = logging.getLogger(__name__)

_PROMPT_PATH = (
    Path(__file__).parent.parent.parent.parent / "prompts" / "cross_file_agent.txt"
)


class CrossFileAgent(ReviewAgent):
    """Tier-3 agent that performs cross-file consistency analysis,
    detecting interface mismatches, broken contracts, and inconsistent
    patterns across related files in the same module."""

    name = "cross_file"
    tier = 3
    category = FindingCategory.CONSISTENCY
    cognitive_mode = "comparative"

    def __init__(
        self,
        llm_client=None,
        tool_provider=None,
        memory_loader=None,
    ) -> None:
        self._llm_client = llm_client
        self._tool_provider = tool_provider
        self._memory_loader = memory_loader

    # ------------------------------------------------------------------
    # Prompt / memory
    # ------------------------------------------------------------------

    def get_system_prompt(self) -> str:
        if _PROMPT_PATH.exists():
            return _PROMPT_PATH.read_text(encoding="utf-8")
        return (
            "You are an expert code reviewer specializing in cross-file "
            "consistency analysis. Compare the files in the group for: "
            "interface mismatches, broken contracts between callers and "
            "callees, inconsistent error handling patterns, naming "
            "inconsistencies, and missing or contradictory imports. Use "
            "tools to explore additional context. Output findings as a "
            "JSON array. Each finding must reference which files are "
            "involved."
        )

    def get_semantic_memory(self) -> list[MemoryDocument]:
        if not self._memory_loader:
            return []
        docs: list[MemoryDocument] = []
        conv = self._memory_loader.load_project_conventions(None)
        if conv:
            docs.append(conv)
        return docs

    # ------------------------------------------------------------------
    # Review (single-file delegates to group)
    # ------------------------------------------------------------------

    def review_file(self, context: FileReviewContext) -> AgentResult:
        """Delegate single-file review to review_file_group with a
        one-file group."""
        group_ctx = FileGroupReviewContext(
            file_group=[context],
            module_name=str(Path(context.file_path).parent),
        )
        return self.review_file_group(group_ctx)

    def review_file_group(self, context: FileGroupReviewContext) -> AgentResult:
        start = time.time()
        tool_calls_log: list[ToolCallRecord] = []

        if not self._llm_client:
            return AgentResult(
                agent_name=self.name,
                errors=["No LLM client configured"],
            )

        if not context.file_group:
            return AgentResult(
                agent_name=self.name,
                errors=["Empty file group"],
                duration_seconds=round(time.time() - start, 2),
            )

        try:
            system_prompt = self.get_system_prompt()
            user_message = self._build_group_user_message(context)

            tools = (
                self._tool_provider.get_tool_descriptions()
                if self._tool_provider
                else None
            )

            if tools and hasattr(self._llm_client, "_get_client"):
                content, tool_calls_log, model, in_tok, out_tok, cost = (
                    self._run_tool_loop(
                        system_prompt, user_message, tools, tool_calls_log
                    )
                )
            else:
                response = self._llm_client.call(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    output_schema={"type": "array"},
                )
                if not response.success:
                    return AgentResult(
                        agent_name=self.name,
                        model_used=response.model,
                        errors=[response.error or "LLM call failed"],
                        duration_seconds=round(time.time() - start, 2),
                    )
                content = response.content
                model = response.model
                in_tok = response.input_tokens
                out_tok = response.output_tokens
                cost = response.cost_usd

            # Use first file as default for findings that don't specify a file
            default_file = context.file_group[0].file_path
            findings = self._parse_findings(content, default_file)

            return AgentResult(
                agent_name=self.name,
                findings=findings,
                tool_calls=tool_calls_log,
                model_used=model,
                input_tokens=in_tok,
                output_tokens=out_tok,
                cost_usd=cost,
                duration_seconds=round(time.time() - start, 2),
            )
        except Exception as e:
            logger.error(
                "CrossFileAgent failed on module %s: %s",
                context.module_name,
                e,
            )
            return AgentResult(
                agent_name=self.name,
                errors=[str(e)],
                duration_seconds=round(time.time() - start, 2),
            )

    # ------------------------------------------------------------------
    # Tool-use loop (Anthropic protocol)
    # ------------------------------------------------------------------

    def _run_tool_loop(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[dict],
        tool_calls_log: list[ToolCallRecord],
        max_iterations: int = 12,
    ) -> tuple[Any, list[ToolCallRecord], str, int, int, float]:
        """Drive the Anthropic tool-use conversation loop."""
        client = self._llm_client._get_client()
        model = getattr(self._llm_client, "_primary_model", "claude-sonnet-4-20250514")

        messages: list[dict] = [{"role": "user", "content": user_message}]
        total_in = 0
        total_out = 0
        total_cost = 0.0

        for _ in range(max_iterations):
            response = client.messages.create(
                model=model,
                max_tokens=8192,
                temperature=0,
                system=system_prompt,
                messages=messages,
                tools=tools,
            )

            total_in += response.usage.input_tokens
            total_out += response.usage.output_tokens
            total_cost += self._compute_cost(
                model, response.usage.input_tokens, response.usage.output_tokens
            )

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})

                tool_results: list[dict] = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self._tool_provider.execute_tool(
                            block.name, block.input
                        )
                        tool_calls_log.append(
                            ToolCallRecord(
                                tool_name=block.name,
                                arguments=block.input,
                                result_summary=result[:200],
                            )
                        )
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result[:5000],
                            }
                        )
                messages.append({"role": "user", "content": tool_results})
            else:
                text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        text += block.text
                return (
                    self._try_parse_json(text),
                    tool_calls_log,
                    model,
                    total_in,
                    total_out,
                    total_cost,
                )

        return [], tool_calls_log, model, total_in, total_out, total_cost

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_group_user_message(
        self, context: FileGroupReviewContext
    ) -> str:
        module = context.module_name or "unknown"
        parts = [f"## File Group: {module}\n"]

        for file_ctx in context.file_group:
            parts.append(f"### {file_ctx.file_path}\n")
            if file_ctx.diff_content:
                parts.append(
                    f"#### Diff\n```\n{file_ctx.diff_content[:2000]}\n```\n"
                )
            parts.append(
                f"#### Content\n```\n{file_ctx.file_content[:4000]}\n```\n"
            )
            if file_ctx.tier1_findings:
                parts.append("#### Tier 1 Findings\n")
                for f in file_ctx.tier1_findings[:5]:
                    parts.append(
                        f"- [{f.severity.name}] {f.title} "
                        f"(line {f.start_line})\n"
                    )

        for file_ctx in context.file_group:
            for mem in file_ctx.semantic_memory:
                parts.append(
                    f"\n## Knowledge: {mem.name}\n{mem.content[:2000]}\n"
                )
                break  # Only include memory once

        parts.append(
            "\n\nAnalyze cross-file consistency. Look for interface "
            "mismatches, broken contracts, inconsistent patterns, and "
            "missing integrations across these files. Use tools to "
            "explore additional files. Output findings as a JSON array."
        )
        return "\n".join(parts)

    @staticmethod
    def _try_parse_json(text: str) -> Any:
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass
        if "```json" in text:
            try:
                return json.loads(
                    text.split("```json")[-1].split("```")[0].strip()
                )
            except (json.JSONDecodeError, TypeError):
                pass
        if "```" in text:
            try:
                return json.loads(text.split("```")[1].split("```")[0].strip())
            except (json.JSONDecodeError, TypeError, IndexError):
                pass
        return text

    @staticmethod
    def _compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        from qa_platform.infrastructure.llm_client import MODEL_COSTS

        costs = MODEL_COSTS.get(model, {"input": 3.0, "output": 15.0})
        return (
            input_tokens * costs["input"] + output_tokens * costs["output"]
        ) / 1_000_000

    def _parse_findings(self, content: Any, default_file: str):
        findings = []
        items: list[dict] = []
        if isinstance(content, list):
            items = content
        elif isinstance(content, dict) and "findings" in content:
            items = content["findings"]
        elif isinstance(content, str):
            try:
                parsed = json.loads(content)
                items = (
                    parsed
                    if isinstance(parsed, list)
                    else parsed.get("findings", [])
                )
            except (json.JSONDecodeError, AttributeError):
                return findings

        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                sev_str = str(item.get("severity", "medium")).upper()
                severity = getattr(Severity, sev_str, Severity.MEDIUM)

                # Cross-file evidence includes references to multiple files
                code_refs = item.get("evidence", {}).get("code_references", [])
                # Also accept "files_involved" as cross-file evidence
                files_involved = item.get("files_involved", [])
                if files_involved and not code_refs:
                    code_refs = files_involved

                evidence = Evidence(
                    tool_calls=item.get("evidence", {}).get("tool_calls", []),
                    code_references=code_refs,
                )
                findings.append(
                    FindingFactory.create_from_agent(
                        agent_name=self.name,
                        tier=self.tier,
                        category=self.category,
                        file=item.get("file", default_file),
                        start_line=int(
                            item.get("start_line", item.get("line", 1))
                        ),
                        end_line=int(
                            item.get(
                                "end_line",
                                item.get("start_line", item.get("line", 1)),
                            )
                        ),
                        severity=severity,
                        title=str(item.get("title", ""))[:120],
                        explanation=str(item.get("explanation", "")),
                        evidence=evidence,
                        recommendation=str(item.get("recommendation", "")),
                    )
                )
            except (ValueError, TypeError, KeyError) as e:
                logger.debug("Skipping malformed cross-file finding: %s", e)
        return findings
