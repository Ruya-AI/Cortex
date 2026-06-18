from __future__ import annotations

import json
import logging
from pathlib import Path

from qa_platform.core.finding import Finding, FindingCategory, Severity
from qa_platform.core.finding_factory import FindingFactory
from qa_platform.tools.base import Tier1Tool

logger = logging.getLogger(__name__)

_SEV_MAP = {
    "CRITICAL": Severity.CRITICAL,
    "HIGH": Severity.HIGH,
    "MEDIUM": Severity.MEDIUM,
    "LOW": Severity.LOW,
    "UNKNOWN": Severity.MEDIUM,
}


class TrivyTool(Tier1Tool):
    name: str = "trivy"

    def is_available(self) -> bool:
        return self._check_binary("trivy")

    def is_applicable(self, file_path: str) -> bool:
        basename = Path(file_path).name
        if basename.startswith("Dockerfile"):
            return True
        return basename in ("requirements.txt", "package.json")

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        try:
            rc, stdout, stderr = self._run_command(
                ["trivy", "fs", "--format", "json", "--quiet", file_path],
                cwd=repo_path,
            )
        except Exception:
            logger.warning("trivy: unexpected error running on %s", file_path)
            return []

        if not stdout.strip():
            return []

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("trivy: failed to parse JSON output for %s", file_path)
            return []

        findings: list[Finding] = []
        for result in data.get("Results", []):
            for vuln in result.get("Vulnerabilities", []):
                vuln_id = vuln.get("VulnerabilityID", "UNKNOWN")
                title = vuln.get("Title", "No title")
                pkg = vuln.get("PkgName", "unknown")
                sev_str = vuln.get("Severity", "UNKNOWN").upper()
                severity = _SEV_MAP.get(sev_str, Severity.MEDIUM)
                findings.append(
                    FindingFactory.create_from_tool(
                        tool_name=self.name,
                        file=file_path,
                        start_line=1,
                        end_line=1,
                        severity=severity,
                        category=FindingCategory.SECURITY,
                        title=f"[{vuln_id}] {title} (pkg: {pkg})",
                        explanation=title,
                        recommendation=f"Update package '{pkg}' to fix {vuln_id}.",
                    )
                )
        return findings
