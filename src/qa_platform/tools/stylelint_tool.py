from __future__ import annotations

import json
import logging
from pathlib import Path

from qa_platform.core.finding import Finding, FindingCategory, Severity
from qa_platform.core.finding_factory import FindingFactory
from qa_platform.tools.base import Tier1Tool

logger = logging.getLogger(__name__)

_SEV_MAP = {
    "error": Severity.HIGH,
    "warning": Severity.MEDIUM,
}


class StylelintTool(Tier1Tool):
    name: str = "stylelint"

    def is_available(self) -> bool:
        return self._check_binary("stylelint")

    def is_applicable(self, file_path: str) -> bool:
        return Path(file_path).suffix in (".css", ".scss", ".less")

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        try:
            rc, stdout, stderr = self._run_command(
                ["stylelint", "--formatter", "json", file_path],
                cwd=repo_path,
            )
        except Exception:
            logger.warning("stylelint: unexpected error running on %s", file_path)
            return []

        if not stdout.strip():
            return []

        try:
            items = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("stylelint: failed to parse JSON output for %s", file_path)
            return []

        findings: list[Finding] = []
        for item in items:
            for warning in item.get("warnings", []):
                line = warning.get("line", 1)
                rule = warning.get("rule", "unknown")
                text = warning.get("text", "")
                sev_str = warning.get("severity", "warning").lower()
                severity = _SEV_MAP.get(sev_str, Severity.MEDIUM)
                findings.append(
                    FindingFactory.create_from_tool(
                        tool_name=self.name,
                        file=file_path,
                        start_line=line,
                        end_line=line,
                        severity=severity,
                        category=FindingCategory.DESIGN,
                        title=f"[{rule}] {text}",
                        explanation=text,
                        recommendation=f"Fix stylelint rule '{rule}'.",
                    )
                )
        return findings
