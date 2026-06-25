from __future__ import annotations

import json
import logging
from pathlib import Path

from cortex_engine.core.finding import Finding, FindingCategory, Severity
from cortex_engine.core.finding_factory import FindingFactory
from cortex_engine.tools.base import Tier1Tool

logger = logging.getLogger(__name__)


class RuffTool(Tier1Tool):
    name: str = "ruff"

    def is_available(self) -> bool:
        return self._check_binary("ruff")

    def is_applicable(self, file_path: str) -> bool:
        return file_path.endswith(".py")

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        rc, stdout, stderr = self._run_command(
            ["ruff", "check", "--output-format=json", "--no-fix", file_path],
            cwd=repo_path,
        )
        if not stdout.strip():
            return []
        try:
            items = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("ruff: failed to parse JSON output for %s", file_path)
            return []

        findings: list[Finding] = []
        for item in items:
            code = item.get("code", "")
            severity = self._map_severity(code)
            start_line = item.get("location", {}).get("row", 1)
            end_line = item.get("end_location", {}).get("row", start_line)
            message = item.get("message", "")
            findings.append(
                FindingFactory.create_from_tool(
                    tool_name=self.name,
                    file=item.get("filename", file_path),
                    start_line=start_line,
                    end_line=end_line,
                    severity=severity,
                    category=FindingCategory.CORRECTNESS,
                    title=f"[{code}] {message}",
                    explanation=message,
                    recommendation=f"Fix ruff {code} violation.",
                )
            )
        return findings

    @staticmethod
    def _map_severity(code: str) -> Severity:
        if not code:
            return Severity.LOW
        first = code[0].upper()
        if first in ("E", "F"):
            return Severity.HIGH
        if first == "W":
            return Severity.MEDIUM
        return Severity.LOW
