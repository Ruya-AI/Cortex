from __future__ import annotations

import json
import logging
from pathlib import Path

from cortex_engine.core.finding import Finding, FindingCategory, Severity
from cortex_engine.core.finding_factory import FindingFactory
from cortex_engine.tools.base import Tier1Tool

logger = logging.getLogger(__name__)


class CheckovTool(Tier1Tool):
    name: str = "checkov"

    def is_available(self) -> bool:
        return self._check_binary("checkov")

    def is_applicable(self, file_path: str) -> bool:
        basename = Path(file_path).name
        if basename.startswith("Dockerfile"):
            return True
        return file_path.endswith((".tf", ".yml", ".yaml"))

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        rc, stdout, stderr = self._run_command(
            ["checkov", "-f", file_path, "--output", "json", "--quiet"],
            cwd=repo_path, timeout=120,
        )
        if not stdout.strip():
            return []
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("checkov: failed to parse JSON output for %s", file_path)
            return []
        # checkov may return a list of check-type blocks or a single dict
        if isinstance(data, list):
            blocks = data
        else:
            blocks = [data]
        findings: list[Finding] = []
        for block in blocks:
            failed = block.get("results", {}).get("failed_checks", [])
            for check in failed:
                check_id = check.get("check_id", "")
                line_range = check.get("file_line_range", [1, 1])
                start = line_range[0] if len(line_range) > 0 else 1
                end = line_range[1] if len(line_range) > 1 else start
                guideline = check.get("guideline", "")
                result = check.get("check_result", {}).get("result", "FAILED")
                findings.append(FindingFactory.create_from_tool(
                    tool_name=self.name, file=file_path,
                    start_line=start, end_line=end, severity=Severity.HIGH,
                    category=FindingCategory.SECURITY,
                    title=f"[{check_id}] {result}",
                    explanation=guideline,
                    recommendation=f"Address checkov check {check_id}. See: {guideline}",
                ))
        return findings
