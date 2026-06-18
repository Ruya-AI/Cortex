from __future__ import annotations

import json
import logging
from pathlib import Path

from qa_platform.core.finding import Finding, FindingCategory, Severity
from qa_platform.core.finding_factory import FindingFactory
from qa_platform.tools.base import Tier1Tool

logger = logging.getLogger(__name__)


class SqlfluffTool(Tier1Tool):
    name: str = "sqlfluff"

    def is_available(self) -> bool:
        return self._check_binary("sqlfluff")

    def is_applicable(self, file_path: str) -> bool:
        return file_path.endswith(".sql")

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        rc, stdout, stderr = self._run_command(
            ["sqlfluff", "lint", "--format", "json", file_path], cwd=repo_path,
        )
        if not stdout.strip():
            return []
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("sqlfluff: failed to parse JSON output for %s", file_path)
            return []
        findings: list[Finding] = []
        for file_entry in data:
            violations = file_entry.get("violations", [])
            for v in violations:
                start = v.get("start_line_no", 1)
                end = v.get("end_line_no", start)
                code = v.get("code", "")
                desc = v.get("description", "")
                findings.append(FindingFactory.create_from_tool(
                    tool_name=self.name, file=file_path,
                    start_line=start, end_line=end, severity=Severity.MEDIUM,
                    category=FindingCategory.CORRECTNESS,
                    title=f"[{code}] {desc}",
                    explanation=desc,
                    recommendation=f"Fix sqlfluff rule {code}.",
                ))
        return findings
