from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

from qa_platform.core.finding import Finding, FindingCategory, Severity
from qa_platform.core.finding_factory import FindingFactory
from qa_platform.tools.base import Tier1Tool

logger = logging.getLogger(__name__)

_APPLICABLE_EXTENSIONS = (".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".java")


class JscpdTool(Tier1Tool):
    name: str = "jscpd"

    def is_available(self) -> bool:
        return self._check_binary("jscpd")

    def is_applicable(self, file_path: str) -> bool:
        return file_path.endswith(_APPLICABLE_EXTENSIONS)

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        with tempfile.TemporaryDirectory() as tmpdir:
            rc, stdout, stderr = self._run_command(
                ["jscpd", file_path, "--reporters", "json",
                 "--output", tmpdir, "--silent"],
                cwd=repo_path,
            )
            report_path = Path(tmpdir) / "jscpd-report.json"
            if not report_path.exists():
                return []
            try:
                data = json.loads(report_path.read_text())
            except (json.JSONDecodeError, OSError):
                logger.warning("jscpd: failed to read report for %s", file_path)
                return []
        duplicates = data.get("duplicates", [])
        findings: list[Finding] = []
        for dup in duplicates:
            lines = dup.get("lines", 0)
            tokens = dup.get("tokens", 0)
            first_file = dup.get("firstFile", {})
            start_line = first_file.get("startLoc", {}).get("line", 1)
            if lines > 50:
                severity = Severity.HIGH
            elif lines > 20:
                severity = Severity.MEDIUM
            else:
                severity = Severity.LOW
            findings.append(FindingFactory.create_from_tool(
                tool_name=self.name, file=file_path,
                start_line=start_line, end_line=start_line + lines,
                severity=severity,
                category=FindingCategory.DESIGN,
                title=f"Code duplication: {lines} lines, {tokens} tokens",
                explanation=(
                    f"Duplicate code block of {lines} lines ({tokens} tokens) "
                    f"detected."
                ),
                recommendation="Refactor duplicated code into a shared function or module.",
            ))
        return findings
