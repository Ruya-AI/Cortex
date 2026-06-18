from __future__ import annotations

import logging
import os

from qa_platform.core.finding import Finding
from qa_platform.core.schemas import IntegrationResult, QualityGateResult
from qa_platform.integrations.dispatcher import IntegrationTarget

logger = logging.getLogger(__name__)


class SlackIntegration(IntegrationTarget):
    """Sends a scan summary to a Slack incoming webhook."""

    name = "slack"

    def __init__(self, webhook_url: str | None = None) -> None:
        self._webhook_url = webhook_url or os.environ.get(
            "SLACK_WEBHOOK_URL", ""
        )

    def is_configured(self) -> bool:
        return bool(self._webhook_url)

    def dispatch(
        self,
        findings: list[Finding],
        gate_result: QualityGateResult,
        scan_metadata: dict,
        config: dict,
    ) -> IntegrationResult:
        try:
            import httpx

            message = self._build_message(findings, gate_result, scan_metadata)
            resp = httpx.post(
                self._webhook_url,
                json={"text": message},
                timeout=30,
            )
            resp.raise_for_status()
            return IntegrationResult(target_name=self.name, status="success")
        except Exception as e:
            logger.error("Slack integration error: %s", e)
            return IntegrationResult(
                target_name=self.name, status="error", error_message=str(e)
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_message(
        findings: list[Finding],
        gate_result: QualityGateResult,
        scan_metadata: dict,
    ) -> str:
        repo = scan_metadata.get("repository", "unknown")
        branch = scan_metadata.get("branch", "")
        sev = gate_result.severity_counts

        status_emoji = ":white_check_mark:" if gate_result.status == "pass" else ":x:"

        lines = [
            f"{status_emoji} *QA Platform Scan* -- `{repo}`",
        ]
        if branch:
            lines.append(f"Branch: `{branch}`")
        lines.extend(
            [
                f"*Gate*: {gate_result.status.upper()} | *Findings*: {len(findings)}",
                (
                    f"Critical: {sev.get('critical', 0)} | "
                    f"High: {sev.get('high', 0)} | "
                    f"Medium: {sev.get('medium', 0)} | "
                    f"Low: {sev.get('low', 0)}"
                ),
            ]
        )
        if gate_result.reasoning:
            lines.append(f"_{gate_result.reasoning}_")

        return "\n".join(lines)
