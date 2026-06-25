from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from cortex_engine.agents.base import ReviewAgent
from cortex_engine.core.finding import (
    Evidence,
    Finding,
    FindingCategory,
    Severity,
    ValidationStatus,
)
from cortex_engine.core.finding_factory import FindingFactory
from cortex_engine.core.schemas import (
    AgentResult,
    FileReviewContext,
    MemoryDocument,
    ToolCallRecord,
)

logger = logging.getLogger(__name__)

_PROMPT_PATH = (
    Path(__file__).parent.parent.parent.parent / "prompts" / "security_agent.txt"
)

# Tier-1 SAST tool names whose findings we fail-open with
_SAST_TOOLS = {"bandit", "semgrep", "gitleaks"}


class SecurityAgent(ReviewAgent):
    """Tier-2 agent that validates SAST findings and detects additional
    security vulnerabilities through adversarial analysis."""

    name = "security"
    tier = 2
    category = FindingCategory.SECURITY
    cognitive_mode = "adversarial"

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
            "You are an adversarial security reviewer. Your mission is to "
            "validate SAST findings and discover security vulnerabilities "
            "that static tools miss. Think like an attacker. Trace data flow "
            "from untrusted sources to sensitive sinks. Use the provided tools "
            "to explore code context. For each finding, provide: title, "
            "severity, explanation, evidence, recommendation, cwe, "
            "validation_status (confirmed/likely/uncertain/suppressed), and "
            "validation_reasoning. Output findings as a JSON array."
        )

    def get_semantic_memory(self) -> list[MemoryDocument]:
        if not self._memory_loader:
            return []
        docs: list[MemoryDocument] = []
        sast_rules = self._memory_loader.load_sast_rules()
        if sast_rules:
            docs.append(sast_rules)
        cwe_tree = self._memory_loader.load_cwe_tree()
        if cwe_tree:
            docs.append(cwe_tree)
        return docs

    # ------------------------------------------------------------------
    # Review
    # ------------------------------------------------------------------

    def review_file(self, context: FileReviewContext) -> AgentResult:
        start = time.time()
        tool_calls_log: list[ToolCallRecord] = []

        if not self._llm_client:
            # CRITICAL fail-open: return all SAST tier1 findings as-is
            sast_findings = self._extract_sast_findings(context)
            return AgentResult(
                agent_name=self.name,
                findings=sast_findings,
                errors=["No LLM client configured — fail-open with raw SAST findings"],
                duration_seconds=round(time.time() - start, 2),
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
                    # CRITICAL fail-open: LLM failed — retain all SAST findings
                    sast_findings = self._extract_sast_findings(context)
                    return AgentResult(
                        agent_name=self.name,
                        findings=sast_findings,
                        errors=[
                            response.error or "LLM call failed",
                            "Fail-open: retaining raw SAST findings unvalidated",
                        ],
                        duration_seconds=round(time.time() - start, 2),
                    )
                content = response.content
                model = response.model
                in_tok = response.input_tokens
                out_tok = response.output_tokens
                cost = response.cost_usd

            findings = self._parse_findings(content, context.file_path)

            # Fail-open: if LLM produced zero findings but we had SAST input,
            # retain the SAST findings as UNVALIDATED.
            if not findings:
                sast_findings = self._extract_sast_findings(context)
                if sast_findings:
                    logger.warning(
                        "Security agent produced zero findings despite %d SAST inputs "
                        "— retaining SAST findings (fail-open)",
                        len(sast_findings),
                    )
                    for f in sast_findings:
                        f.validation_status = ValidationStatus.UNVALIDATED
                        f.validation_reasoning = (
                            "Security agent produced no output — SAST finding retained (fail-open)"
                        )
                    return AgentResult(
                        agent_name=self.name,
                        findings=sast_findings,
                        tool_calls=tool_calls_log,
                        model_used=model,
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        cost_usd=cost,
                        errors=["Fail-open: LLM produced no findings despite SAST inputs"],
                        duration_seconds=round(time.time() - start, 2),
                    )

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
            logger.error("SecurityAgent failed on %s: %s", context.file_path, e)
            # CRITICAL fail-open
            sast_findings = self._extract_sast_findings(context)
            return AgentResult(
                agent_name=self.name,
                findings=sast_findings,
                errors=[
                    str(e),
                    "Fail-open: retaining raw SAST findings unvalidated",
                ],
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

        # SAST findings first — these are what the security agent validates
        sast_items = [
            f
            for f in context.tier1_findings
            if f.source.lower() in _SAST_TOOLS
        ]
        if sast_items:
            parts.append("## SAST Findings to Validate\n")
            for f in sast_items:
                cwe_note = f" (CWE: {f.cwe})" if f.cwe else ""
                parts.append(
                    f"- [{f.severity.name}] {f.title}{cwe_note} "
                    f"at line {f.start_line} (source: {f.source})\n"
                )

        # Other tier1 findings
        other_t1 = [
            f
            for f in context.tier1_findings
            if f.source.lower() not in _SAST_TOOLS
        ]
        if other_t1:
            parts.append("## Other Tier 1 Findings\n")
            for f in other_t1[:5]:
                parts.append(
                    f"- [{f.severity.name}] {f.title} (line {f.start_line})\n"
                )

        if context.diff_content:
            parts.append(f"## Diff\n<CODE_FOR_REVIEW>\n{context.diff_content[:3000]}\n</CODE_FOR_REVIEW>\n")
        parts.append(f"## File Content\n<CODE_FOR_REVIEW>\n{context.file_content[:8000]}\n</CODE_FOR_REVIEW>\n")

        for mem in context.semantic_memory:
            parts.append(f"\n## Knowledge: {mem.name}\n{mem.content[:2000]}\n")

        parts.append(
            "\n\nValidate the SAST findings above and search for additional "
            "security issues. Use tools to trace data flow. Output findings "
            "as a JSON array with validation_status and validation_reasoning "
            "for each."
        )
        return "\n".join(parts)

    @staticmethod
    def _extract_sast_findings(context: FileReviewContext) -> list[Finding]:
        """Fail-open: return tier1 SAST findings with UNVALIDATED status."""
        results: list[Finding] = []
        for f in context.tier1_findings:
            if f.source.lower() in _SAST_TOOLS:
                f.validation_status = ValidationStatus.UNVALIDATED
                results.append(f)
        return results

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
        from cortex_engine.infrastructure.llm_client import MODEL_COSTS

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
                cwe = item.get("cwe") or None

                finding = FindingFactory.create_from_agent(
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
                    cwe=cwe,
                )

                # Apply validation verdict if present
                vs = item.get("validation_status", "").lower()
                if vs and hasattr(ValidationStatus, vs.upper()):
                    finding.validation_status = ValidationStatus(vs)
                vr = item.get("validation_reasoning", "")
                if vr:
                    finding.validation_reasoning = str(vr)

                findings.append(finding)
            except (ValueError, TypeError, KeyError) as e:
                logger.debug("Skipping malformed security finding: %s", e)
        return findings
