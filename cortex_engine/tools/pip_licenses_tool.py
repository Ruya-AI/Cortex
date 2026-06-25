from __future__ import annotations

import json
import logging
from pathlib import Path

from cortex_engine.core.finding import Finding, FindingCategory, Severity
from cortex_engine.core.finding_factory import FindingFactory
from cortex_engine.tools.base import Tier1Tool

logger = logging.getLogger(__name__)

_COPYLEFT_KEYWORDS = ("GPL", "AGPL", "LGPL", "Copyleft", "SSPL")


class PipLicensesTool(Tier1Tool):
    name: str = "pip-licenses"

    def is_available(self) -> bool:
        return self._check_binary("pip-licenses")

    def is_applicable(self, file_path: str) -> bool:
        basename = Path(file_path).name
        return basename in ("requirements.txt", "setup.py", "pyproject.toml")

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        rc, stdout, stderr = self._run_command(
            ["pip-licenses", "--format=json"], cwd=repo_path,
        )
        if not stdout.strip():
            return []
        try:
            packages = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("pip-licenses: failed to parse JSON output")
            return []
        findings: list[Finding] = []
        for pkg in packages:
            license_name = pkg.get("License", "")
            pkg_name = pkg.get("Name", "unknown")
            if any(kw in license_name for kw in _COPYLEFT_KEYWORDS):
                findings.append(FindingFactory.create_from_tool(
                    tool_name=self.name, file=file_path,
                    start_line=1, end_line=1, severity=Severity.MEDIUM,
                    category=FindingCategory.SECURITY,
                    title=f"Copyleft license: {pkg_name} ({license_name})",
                    explanation=(
                        f"Dependency '{pkg_name}' uses copyleft license "
                        f"'{license_name}', which may impose distribution "
                        f"obligations on your project."
                    ),
                    recommendation=f"Review license compatibility for {pkg_name}.",
                ))
        return findings
