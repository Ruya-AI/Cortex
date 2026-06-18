from __future__ import annotations

import json
import logging
from pathlib import Path

from qa_platform.core.finding import Finding, FindingCategory, Severity
from qa_platform.core.finding_factory import FindingFactory
from qa_platform.tools.base import Tier1Tool

logger = logging.getLogger(__name__)

_APPLICABLE_NAMES = frozenset(("requirements.txt", "setup.py", "pyproject.toml"))


class PipAuditTool(Tier1Tool):
    name: str = "pip-audit"

    def is_available(self) -> bool:
        return self._check_binary("pip-audit")

    def is_applicable(self, file_path: str) -> bool:
        return Path(file_path).name in _APPLICABLE_NAMES

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        filename = Path(file_path).name
        if filename == "requirements.txt":
            cmd = ["pip-audit", "--format=json", "-r", file_path]
        else:
            cmd = ["pip-audit", "--format=json"]
        rc, stdout, stderr = self._run_command(cmd, cwd=repo_path, timeout=120)
        if not stdout.strip():
            return []
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("pip-audit: failed to parse JSON output for %s", file_path)
            return []

        dependencies = data.get("dependencies", [])
        findings: list[Finding] = []
        for dep in dependencies:
            dep_name = dep.get("name", "unknown")
            dep_version = dep.get("version", "unknown")
            vulns = dep.get("vulns", [])
            for vuln in vulns:
                vuln_id = vuln.get("id", "")
                description = vuln.get("description", "")
                fix_versions = vuln.get("fix_versions", [])
                fix_str = ", ".join(fix_versions) if fix_versions else "no fix available"
                findings.append(
                    FindingFactory.create_from_tool(
                        tool_name=self.name,
                        file=file_path,
                        start_line=1,
                        end_line=1,
                        severity=Severity.HIGH,
                        category=FindingCategory.SECURITY,
                        title=f"[{vuln_id}] Vulnerability in {dep_name}=={dep_version}",
                        explanation=description or f"Known vulnerability {vuln_id} in {dep_name}.",
                        recommendation=f"Upgrade {dep_name} to one of: {fix_str}.",
                    )
                )
        return findings
