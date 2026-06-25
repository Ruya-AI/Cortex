from __future__ import annotations

import json
import logging
from pathlib import Path

from cortex_engine.core.finding import Finding, FindingCategory, Severity
from cortex_engine.core.finding_factory import FindingFactory
from cortex_engine.tools.base import Tier1Tool

logger = logging.getLogger(__name__)

_LEVEL_MAP = {
    "error": Severity.HIGH,
    "warning": Severity.MEDIUM,
    "info": Severity.LOW,
    "style": Severity.INFO,
}


class ShellcheckTool(Tier1Tool):
    name: str = "shellcheck"

    def is_available(self) -> bool:
        return self._check_binary("shellcheck")

    def is_applicable(self, file_path: str) -> bool:
        return Path(file_path).suffix in (".sh", ".bash")

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        rc, stdout, stderr = self._run_command(
            ["shellcheck", "-f", "json", file_path],
            cwd=repo_path,
        )
        if not stdout.strip():
            return []
        try:
            items = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("shellcheck: failed to parse JSON output for %s", file_path)
            return []

        findings: list[Finding] = []
        for item in items:
            level = item.get("level", "warning").lower()
            severity = _LEVEL_MAP.get(level, Severity.MEDIUM)
            start_line = item.get("line", 1)
            end_line = item.get("endLine", start_line)
            message = item.get("message", "")
            code = item.get("code", "")
            findings.append(
                FindingFactory.create_from_tool(
                    tool_name=self.name,
                    file=item.get("file", file_path),
                    start_line=start_line,
                    end_line=end_line,
                    severity=severity,
                    category=FindingCategory.CORRECTNESS,
                    title=f"[SC{code}] {message}",
                    explanation=message,
                    recommendation=f"Fix shellcheck issue SC{code}.",
                )
            )
        return findings
