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
)
from qa_platform.core.finding_factory import FindingFactory
from qa_platform.core.schemas import (
    AgentResult,
    FileReviewContext,
    MemoryDocument,
    ToolCallRecord,
)

logger = logging.getLogger(__name__)

_PROMPT_PATH = (
    Path(__file__).parent.parent.parent.parent / "prompts" / "design_agent.txt"
)


class DesignAgent(ReviewAgent):
    """Tier-2 agent that evaluates code structure, design patterns,
    modularity, and adherence to design principles."""

    name = "design"
    tier = 2
    category = FindingCategory.DESIGN
    cognitive_mode = "evaluative"

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
            "You are an expert software architect reviewing code for design "
            "quality. Evaluate structure, not behavior. Focus on: SOLID "
            "principles, coupling and cohesion, abstraction levels, naming "
            "clarity, separation of concerns, and API ergonomics. Suggest "
            "improvements, not bug reports. Use the provided tools to explore "
            "the broader codebase context. Output findings as a JSON array."
        )

    def get_semantic_memory(self) -> list[MemoryDocument]:
        if not self._memory_loader:
            return []
        docs: list[MemoryDocument] = []
        principles = self._memory_loader.load_design_principles()
        if principles:
            docs.append(principles)
        return docs

    # ------------------------------------------------------------------
    # Review
    # ------------------------------------------------------------------

    def review_file(self, context: FileReviewContext) -> AgentResult:
        start = time.time()
        tool_calls_log: list[ToolCallRecord] = []

        if not self._llm_client:
            return AgentResult(
                agent_name=self.name,
                errors=["No LLM client configured"],
            )

        try:
            system_prompt = self.get_system_prompt()
            user_message = self._build_user_message(context)

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

            findings = self._parse_findings(content, context.file_path)

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
            logger.error("DesignAgent failed on %s: %s", context.file_path, e)
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
        max_iterations: int = 10,
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

    def _build_user_message(self, context: FileReviewContext) -> str:
        parts = [f"## File Under Review: {context.file_path}\n"]
        if context.diff_content:
            parts.append(f"## Diff\n<CODE_FOR_REVIEW>\n{context.diff_content[:3000]}\n</CODE_FOR_REVIEW>\n")
        parts.append(f"## File Content\n<CODE_FOR_REVIEW>\n{context.file_content[:8000]}\n</CODE_FOR_REVIEW>\n")

        # Design agents look at tier1 findings for complexity/style signals
        if context.tier1_findings:
            parts.append("## Tier 1 Signals\n")
            for f in context.tier1_findings[:10]:
                parts.append(
                    f"- [{f.severity.name}] {f.title} (line {f.start_line}, "
                    f"source: {f.source})\n"
                )

        for mem in context.semantic_memory:
            parts.append(f"\n## Knowledge: {mem.name}\n{mem.content[:2000]}\n")

        parts.append(
            "\n\nEvaluate structure, not behavior. Suggest improvements, "
            "not bug reports. Use tools to explore dependencies and "
            "module boundaries. Output findings as a JSON array."
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

    def _parse_findings(self, content: Any, file_path: str):
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
                evidence = Evidence(
                    tool_calls=item.get("evidence", {}).get("tool_calls", []),
                    code_references=item.get("evidence", {}).get(
                        "code_references", []
                    ),
                )
                findings.append(
                    FindingFactory.create_from_agent(
                        agent_name=self.name,
                        tier=self.tier,
                        category=self.category,
                        file=item.get("file", file_path),
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
                logger.debug("Skipping malformed design finding: %s", e)
        return findings
