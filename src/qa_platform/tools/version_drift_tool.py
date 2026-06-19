from __future__ import annotations

import json
import logging
from pathlib import Path

from qa_platform.core.finding import Finding, FindingCategory, Severity
from qa_platform.core.finding_factory import FindingFactory
from qa_platform.tools.base import Tier1Tool

logger = logging.getLogger(__name__)


class VersionDriftTool(Tier1Tool):
    name: str = "version-drift"

    def is_available(self) -> bool:
        return True

    def is_applicable(self, file_path: str) -> bool:
        return Path(file_path).name in ("requirements.txt", "package.json")

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        full_path = repo_path / file_path
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning("version-drift: cannot read %s: %s", file_path, e)
            return []

        basename = Path(file_path).name
        if basename == "requirements.txt":
            return self._check_requirements(file_path, content)
        return self._check_package_json(file_path, content)

    def _check_requirements(self, file_path: str, content: str) -> list[Finding]:
        findings: list[Finding] = []
        for line_no, raw_line in enumerate(content.splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # A pinned dependency uses ==
            if "==" in line:
                continue
            # Extract package name (everything before the first version specifier)
            pkg = line.split(";")[0].split("[")[0].strip()
            if not pkg:
                continue
            findings.append(
                FindingFactory.create_from_tool(
                    tool_name=self.name,
                    file=file_path,
                    start_line=line_no,
                    end_line=line_no,
                    severity=Severity.MEDIUM,
                    category=FindingCategory.SECURITY,
                    title=f"Unpinned dependency: {pkg}",
                    explanation=(
                        f"'{raw_line.strip()}' does not pin an exact version with ==. "
                        "Unpinned dependencies can introduce breaking changes or vulnerabilities."
                    ),
                    recommendation=f"Pin the dependency to an exact version, e.g. {pkg}==<version>.",
                )
            )
        return findings

    def _check_package_json(self, file_path: str, content: str) -> list[Finding]:
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("version-drift: invalid JSON in %s: %s", file_path, e)
            return []

        findings: list[Finding] = []
        unpinned_markers = ("^", "~", "*", ">=", ">", "latest")
        lines = content.splitlines()

        for section in ("dependencies", "devDependencies"):
            deps = data.get(section, {})
            if not isinstance(deps, dict):
                continue
            for pkg, version in deps.items():
                if not isinstance(version, str):
                    continue
                if any(version.lstrip().startswith(m) for m in unpinned_markers):
                    # Find the line number for this dependency
                    line_no = 1
                    for idx, line in enumerate(lines, start=1):
                        if f'"{pkg}"' in line:
                            line_no = idx
                            break
                    findings.append(
                        FindingFactory.create_from_tool(
                            tool_name=self.name,
                            file=file_path,
                            start_line=line_no,
                            end_line=line_no,
                            severity=Severity.MEDIUM,
                            category=FindingCategory.SECURITY,
                            title=f"Unpinned dependency: {pkg}",
                            explanation=(
                                f"'{pkg}': '{version}' uses a non-exact version specifier. "
                                "This can introduce unexpected breaking changes or vulnerabilities."
                            ),
                            recommendation=f"Pin {pkg} to an exact version, e.g. \"{pkg}\": \"{version.lstrip('^~>= ')}\".",
                        )
                    )
        return findings
