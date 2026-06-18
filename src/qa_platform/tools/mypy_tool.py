from __future__ import annotations

import logging
import re
from pathlib import Path

from qa_platform.core.finding import Finding, FindingCategory, Severity
from qa_platform.core.finding_factory import FindingFactory
from qa_platform.tools.base import Tier1Tool

logger = logging.getLogger(__name__)

_LINE_RE = re.compile(
    r"^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):\s*(?P<level>\w+):\s*(?P<msg>.+)$"
)


class MypyTool(Tier1Tool):
    name: str = "mypy"

    def is_available(self) -> bool:
        return self._check_binary("mypy")

    def is_applicable(self, file_path: str) -> bool:
        return file_path.endswith(".py")

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        rc, stdout, stderr = self._run_command(
            [
                "mypy",
                "--no-error-summary",
                "--no-color-output",
                "--show-column-numbers",
                file_path,
            ],
            cwd=repo_path,
        )
        if not stdout.strip():
            return []

        findings: list[Finding] = []
        for line in stdout.splitlines():
            match = _LINE_RE.match(line.strip())
            if not match:
                continue
            level = match.group("level").lower()
            if level == "error":
                severity = Severity.MEDIUM
            elif level == "note":
                severity = Severity.LOW
            else:
                severity = Severity.LOW
            message = match.group("msg").strip()
            line_no = int(match.group("line"))
            findings.append(
                FindingFactory.create_from_tool(
                    tool_name=self.name,
                    file=match.group("file"),
                    start_line=line_no,
                    end_line=line_no,
                    severity=severity,
                    category=FindingCategory.CORRECTNESS,
                    title=f"[mypy-{level}] {message}",
                    explanation=message,
                    recommendation="Fix the type error reported by mypy.",
                )
            )
        return findings
