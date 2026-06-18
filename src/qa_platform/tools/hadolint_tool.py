from __future__ import annotations

import json
import logging
from pathlib import Path

from qa_platform.core.finding import Finding, FindingCategory, Severity
from qa_platform.core.finding_factory import FindingFactory
from qa_platform.tools.base import Tier1Tool

logger = logging.getLogger(__name__)

_LEVEL_MAP: dict[str, Severity] = {
    "error": Severity.HIGH,
    "warning": Severity.MEDIUM,
    "info": Severity.LOW,
    "style": Severity.INFO,
}


class HadolintTool(Tier1Tool):
    name: str = "hadolint"

    def is_available(self) -> bool:
        return self._check_binary("hadolint")

    def is_applicable(self, file_path: str) -> bool:
        return Path(file_path).name.startswith("Dockerfile")

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        rc, stdout, stderr = self._run_command(
            ["hadolint", "--format", "json", file_path], cwd=repo_path,
        )
        if not stdout.strip():
            return []
        try:
            items = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("hadolint: failed to parse JSON output for %s", file_path)
            return []
        findings: list[Finding] = []
        for item in items:
            line = item.get("line", 1)
            severity = _LEVEL_MAP.get(item.get("level", "warning"), Severity.MEDIUM)
            code = item.get("code", "")
            message = item.get("message", "")
            findings.append(FindingFactory.create_from_tool(
                tool_name=self.name, file=file_path,
                start_line=line, end_line=line, severity=severity,
                category=FindingCategory.SECURITY,
                title=f"[{code}] {message}",
                explanation=message,
                recommendation=f"Fix hadolint rule {code}.",
            ))
        return findings
