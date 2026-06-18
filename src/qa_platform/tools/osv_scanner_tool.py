from __future__ import annotations

import json
import logging
from pathlib import Path

from qa_platform.core.finding import Finding, FindingCategory, Severity
from qa_platform.core.finding_factory import FindingFactory
from qa_platform.tools.base import Tier1Tool

logger = logging.getLogger(__name__)

_APPLICABLE_BASENAMES = {"requirements.txt", "package.json", "go.sum", "Cargo.lock"}


class OsvScannerTool(Tier1Tool):
    name: str = "osv-scanner"

    def is_available(self) -> bool:
        return self._check_binary("osv-scanner")

    def is_applicable(self, file_path: str) -> bool:
        return Path(file_path).name in _APPLICABLE_BASENAMES

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        try:
            rc, stdout, stderr = self._run_command(
                ["osv-scanner", "--json", "-L", file_path],
                cwd=repo_path,
            )
        except Exception:
            logger.warning("osv-scanner: unexpected error running on %s", file_path)
            return []

        if not stdout.strip():
            return []

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("osv-scanner: failed to parse JSON output for %s", file_path)
            return []

        findings: list[Finding] = []
        for result in data.get("results", []):
            for pkg in result.get("packages", []):
                for vuln in pkg.get("vulnerabilities", []):
                    vuln_id = vuln.get("id", "UNKNOWN")
                    summary = vuln.get("summary", "No summary available")
                    findings.append(
                        FindingFactory.create_from_tool(
                            tool_name=self.name,
                            file=file_path,
                            start_line=1,
                            end_line=1,
                            severity=Severity.HIGH,
                            category=FindingCategory.SECURITY,
                            title=f"[{vuln_id}] {summary}",
                            explanation=summary,
                            recommendation=f"Address vulnerability {vuln_id}. Check https://osv.dev/vulnerability/{vuln_id}",
                        )
                    )
        return findings
