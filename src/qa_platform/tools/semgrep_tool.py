from __future__ import annotations

import json
import logging
from pathlib import Path

from qa_platform.core.finding import Finding, FindingCategory, Severity
from qa_platform.core.finding_factory import FindingFactory
from qa_platform.tools.base import Tier1Tool

logger = logging.getLogger(__name__)

_SEMGREP_EXTENSIONS = frozenset(
    (".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".java", ".rb", ".rs")
)

_SEVERITY_MAP = {
    "ERROR": Severity.HIGH,
    "WARNING": Severity.MEDIUM,
    "INFO": Severity.LOW,
}


class SemgrepTool(Tier1Tool):
    name: str = "semgrep"

    def is_available(self) -> bool:
        return self._check_binary("semgrep")

    def is_applicable(self, file_path: str) -> bool:
        return Path(file_path).suffix in _SEMGREP_EXTENSIONS

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        rc, stdout, stderr = self._run_command(
            ["semgrep", "scan", "--json", "--quiet", file_path],
            cwd=repo_path,
        )
        if not stdout.strip():
            return []
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("semgrep: failed to parse JSON output for %s", file_path)
            return []

        results = data.get("results", [])
        findings: list[Finding] = []
        for result in results:
            sev_str = result.get("extra", {}).get("severity", "WARNING").upper()
            severity = _SEVERITY_MAP.get(sev_str, Severity.MEDIUM)
            start_line = result.get("start", {}).get("line", 1)
            end_line = result.get("end", {}).get("line", start_line)
            message = result.get("extra", {}).get("message", "")
            rule_id = result.get("check_id", "")
            findings.append(
                FindingFactory.create_from_tool(
                    tool_name=self.name,
                    file=result.get("path", file_path),
                    start_line=start_line,
                    end_line=end_line,
                    severity=severity,
                    category=FindingCategory.SECURITY,
                    title=f"[{rule_id}] {message}",
                    explanation=message,
                    recommendation=f"Address semgrep finding: {rule_id}.",
                )
            )
        return findings
