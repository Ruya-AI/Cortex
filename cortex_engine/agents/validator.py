from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from cortex_engine.agents.base import ReviewAgent
from cortex_engine.core.finding import (
    Finding,
    FindingCategory,
    ValidationStatus,
)
from cortex_engine.core.schemas import (
    AgentResult,
    FileReviewContext,
    MemoryDocument,
    ToolCallRecord,
    ValidationResult,
)

logger = logging.getLogger(__name__)

_PROMPT_PATH = (
    Path(__file__).parent.parent.parent.parent / "prompts" / "validator_agent.txt"
)

_BATCH_SIZE = 15


class ValidatorAgent(ReviewAgent):
    """Post-detection agent that attempts to refute every finding.

    Unlike the detection agents, the validator does not override
    ``review_file``.  Its primary entry point is :meth:`validate`,
    which takes the full finding list and a repo path and returns a
    :class:`ValidationResult`.
    """

    name = "validator"
    tier = 4
    category = FindingCategory.CORRECTNESS  # irrelevant for validator
    cognitive_mode = "skeptical"

    def __init__(
        self,
        llm_client=None,
        tool_provider=None,
        memory_loader=None,
        *,
        model_override: str | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._tool_provider = tool_provider
        self._memory_loader = memory_loader
        self._model_override = model_override  # default: Opus

    # ------------------------------------------------------------------
    # Prompt / memory
    # ------------------------------------------------------------------

    def get_system_prompt(self) -> str:
        if _PROMPT_PATH.exists():
            return _PROMPT_PATH.read_text(encoding="utf-8")
        return (
            "You are a skeptical code-review validator. Your job is to "
            "REFUTE each finding presented to you. For every finding, "
            "attempt to prove it is wrong — check whether the alleged "
            "issue actually exists in the code, whether context makes it "
            "a non-issue, or whether the severity is overstated. Use tools "
            "to read the actual code. For each finding, respond with: "
            "finding_id, validation_status (confirmed / likely / uncertain "
            "/ suppressed), confidence (high / medium / low), reasoning, "
            "and optionally merged_with (another finding_id if duplicate). "
            "Output as a JSON array."
        )

    def get_semantic_memory(self) -> list[MemoryDocument]:
        return []

    # ------------------------------------------------------------------
    # review_file — minimal implementation to satisfy ABC
    # ------------------------------------------------------------------

    def review_file(self, context: FileReviewContext) -> AgentResult:
        """The validator does not perform per-file detection.

        Calling this is a no-op that returns an empty result.  Use
        :meth:`validate` instead.
        """
        return AgentResult(agent_name=self.name)

    # ------------------------------------------------------------------
    # Primary entry point
    # ------------------------------------------------------------------

    def validate(
        self, findings: list[Finding], repo_path: Path
    ) -> ValidationResult:
        """Validate a list of findings, attempting to refute each one.

        Findings are batched into groups of ``_BATCH_SIZE``.  Each batch
        is sent to the LLM.  If the LLM call fails for a batch, all
        findings in that batch receive ``UNVALIDATED`` status (fail-open).

        Returns a :class:`ValidationResult` with ``validated_findings``
        (those that survived validation) and ``suppressed_findings``
        (those the validator suppressed).
        """
        if not findings:
            return ValidationResult()

        if not self._llm_client:
            # Fail-open: mark everything unvalidated
            for f in findings:
                f.validation_status = ValidationStatus.UNVALIDATED
            return ValidationResult(validated_findings=list(findings))

        system_prompt = self.get_system_prompt()
        validated: list[Finding] = []
        suppressed: list[Finding] = []
        total_tool_calls: list[ToolCallRecord] = []

        # Index findings by id for fast lookup
        findings_by_id: dict[str, Finding] = {}
        for f in findings:
            fid = f.id or f.suppression_key or f"{f.source}:{f.file}:{f.start_line}"
            findings_by_id[fid] = f

        # Process in batches
        batches = [
            findings[i : i + _BATCH_SIZE]
            for i in range(0, len(findings), _BATCH_SIZE)
        ]

        for batch in batches:
            try:
                verdicts = self._validate_batch(
                    batch, system_prompt, repo_path, total_tool_calls
                )
                self._apply_verdicts(batch, verdicts, validated, suppressed)
            except Exception as e:
                logger.error("Validator batch failed: %s — fail-open", e)
                # CRITICAL fail-open: retain all findings as UNVALIDATED
                for f in batch:
                    f.validation_status = ValidationStatus.UNVALIDATED
                    validated.append(f)

        return ValidationResult(
            validated_findings=validated,
            suppressed_findings=suppressed,
            suppressed_count=len(suppressed),
        )

    # ------------------------------------------------------------------
    # Batch processing
    # ------------------------------------------------------------------

    def _validate_batch(
        self,
        batch: list[Finding],
        system_prompt: str,
        repo_path: Path,
        tool_calls_log: list[ToolCallRecord],
    ) -> list[dict]:
        """Send a batch of findings to the LLM for validation.

        Returns a list of verdict dicts from the LLM.
        """
        user_message = self._build_batch_prompt(batch)

        tools = (
            self._tool_provider.get_tool_descriptions()
            if self._tool_provider
            else None
        )

        model = self._model_override

        if tools and hasattr(self._llm_client, "_get_client"):
            content, tool_calls_log[:], _, _, _, _ = self._run_tool_loop(
                system_prompt, user_message, tools, tool_calls_log, model=model,
            )
        else:
            response = self._llm_client.call(
                system_prompt=system_prompt,
                user_message=user_message,
                output_schema={"type": "array"},
                model=model,
            )
            if not response.success:
                raise RuntimeError(response.error or "LLM call failed")
            content = response.content

        return self._parse_verdicts(content)

    def _build_batch_prompt(self, batch: list[Finding]) -> str:
        parts = ["## Findings to Validate\n"]
        parts.append(
            "Attempt to REFUTE each finding below. For each, provide "
            "your verdict.\n\n"
        )

        for f in batch:
            fid = f.id or f.suppression_key or f"{f.source}:{f.file}:{f.start_line}"
            parts.append(f"### Finding: {fid}\n")
            parts.append(f"- **Source**: {f.source}\n")
            parts.append(f"- **File**: {f.file}\n")
            parts.append(f"- **Line**: {f.start_line}-{f.end_line}\n")
            parts.append(f"- **Severity**: {f.severity.name}\n")
            parts.append(f"- **Title**: {f.title}\n")
            parts.append(f"- **Explanation**: {f.explanation[:500]}\n")
            if f.evidence and (f.evidence.tool_calls or f.evidence.code_references):
                evidence_parts = []
                if f.evidence.tool_calls:
                    evidence_parts.append(
                        f"  tool_calls: {f.evidence.tool_calls[:3]}"
                    )
                if f.evidence.code_references:
                    evidence_parts.append(
                        f"  code_refs: {f.evidence.code_references[:3]}"
                    )
                parts.append(f"- **Evidence**: {'; '.join(evidence_parts)}\n")
            if f.cwe:
                parts.append(f"- **CWE**: {f.cwe}\n")
            parts.append("\n")

        parts.append(
            "Use read_file and expand_context to verify each finding "
            "against the actual code. Output a JSON array of verdicts."
        )
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Tool-use loop
    # ------------------------------------------------------------------

    def _run_tool_loop(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[dict],
        tool_calls_log: list[ToolCallRecord],
        max_iterations: int = 15,
        model: str | None = None,
    ) -> tuple[Any, list[ToolCallRecord], str, int, int, float]:
        """Drive the Anthropic tool-use conversation loop."""
        client = self._llm_client._get_client()
        use_model = model or getattr(
            self._llm_client, "_primary_model", "claude-sonnet-4-20250514"
        )

        messages: list[dict] = [{"role": "user", "content": user_message}]
        total_in = 0
        total_out = 0
        total_cost = 0.0

        for _ in range(max_iterations):
            response = client.messages.create(
                model=use_model,
                max_tokens=8192,
                temperature=0,
                system=system_prompt,
                messages=messages,
                tools=tools,
            )

            total_in += response.usage.input_tokens
            total_out += response.usage.output_tokens
            total_cost += self._compute_cost(
                use_model,
                response.usage.input_tokens,
                response.usage.output_tokens,
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
                    use_model,
                    total_in,
                    total_out,
                    total_cost,
                )

        return [], tool_calls_log, use_model, total_in, total_out, total_cost

    # ------------------------------------------------------------------
    # Verdict parsing and application
    # ------------------------------------------------------------------

    def _parse_verdicts(self, content: Any) -> list[dict]:
        """Parse LLM output into a list of verdict dicts."""
        items: list[dict] = []
        if isinstance(content, list):
            items = content
        elif isinstance(content, dict) and "verdicts" in content:
            items = content["verdicts"]
        elif isinstance(content, dict) and "findings" in content:
            items = content["findings"]
        elif isinstance(content, str):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    items = parsed
                elif isinstance(parsed, dict):
                    items = parsed.get(
                        "verdicts", parsed.get("findings", [])
                    )
            except (json.JSONDecodeError, AttributeError):
                pass
        return [v for v in items if isinstance(v, dict)]

    @staticmethod
    def _apply_verdicts(
        batch: list[Finding],
        verdicts: list[dict],
        validated: list[Finding],
        suppressed: list[Finding],
    ) -> None:
        """Apply LLM verdicts to the findings in the batch."""
        # Build verdict lookup by finding_id
        verdict_map: dict[str, dict] = {}
        for v in verdicts:
            fid = v.get("finding_id", "")
            if fid:
                verdict_map[fid] = v

        for f in batch:
            fid = (
                f.id
                or f.suppression_key
                or f"{f.source}:{f.file}:{f.start_line}"
            )
            verdict = verdict_map.get(fid)

            if verdict:
                status_str = str(verdict.get("validation_status", "unvalidated")).lower()
                if hasattr(ValidationStatus, status_str.upper()):
                    f.validation_status = ValidationStatus(status_str)
                else:
                    f.validation_status = ValidationStatus.UNVALIDATED

                reasoning = verdict.get("reasoning", "")
                if reasoning:
                    f.validation_reasoning = str(reasoning)

                merged = verdict.get("merged_with")
                if merged:
                    f.related_findings.append(str(merged))
            else:
                # No verdict from LLM — fail-open
                f.validation_status = ValidationStatus.UNVALIDATED

            if f.validation_status == ValidationStatus.SUPPRESSED:
                suppressed.append(f)
            else:
                validated.append(f)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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

        costs = MODEL_COSTS.get(model, {"input": 15.0, "output": 75.0})
        return (
            input_tokens * costs["input"] + output_tokens * costs["output"]
        ) / 1_000_000
