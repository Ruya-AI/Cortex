from __future__ import annotations

import json
import logging
from pathlib import Path

from qa_platform.core.finding import Finding, FindingCategory, Severity
from qa_platform.core.finding_factory import FindingFactory
from qa_platform.tools.base import Tier1Tool

logger = logging.getLogger(__name__)

_SEVERITY_MAP = {
    "HIGH": Severity.HIGH,
    "MEDIUM": Severity.MEDIUM,
    "LOW": Severity.LOW,
}


class BanditTool(Tier1Tool):
    name: str = "bandit"

    def is_available(self) -> bool:
        return self._check_binary("bandit")

    def is_applicable(self, file_path: str) -> bool:
        return file_path.endswith(".py")

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        rc, stdout, stderr = self._run_command(
            ["bandit", "-f", "json", "-ll", file_path],
            cwd=repo_path,
        )
        if not stdout.strip():
            return []
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("bandit: failed to parse JSON output for %s", file_path)
            return []

        results = data.get("results", [])
        findings: list[Finding] = []
        for result in results:
            severity_str = result.get("issue_severity", "MEDIUM").upper()
            severity = _SEVERITY_MAP.get(severity_str, Severity.MEDIUM)
            line = result.get("line_number", 1)
            line_range = result.get("line_range", [line])
            end_line = max(line_range) if line_range else line
            test_id = result.get("test_id", "")
            issue_text = result.get("issue_text", "")
            findings.append(
                FindingFactory.create_from_tool(
                    tool_name=self.name,
                    file=result.get("filename", file_path),
                    start_line=line,
                    end_line=end_line,
                    severity=severity,
                    category=FindingCategory.SECURITY,
                    title=f"[{test_id}] {issue_text}",
                    explanation=issue_text,
                    recommendation=f"Address bandit finding {test_id}.",
                )
            )
        return findings
