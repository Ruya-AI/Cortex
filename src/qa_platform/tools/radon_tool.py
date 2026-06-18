from __future__ import annotations

import json
import logging
from pathlib import Path

from qa_platform.core.finding import Finding, FindingCategory, Severity
from qa_platform.core.finding_factory import FindingFactory
from qa_platform.tools.base import Tier1Tool

logger = logging.getLogger(__name__)

_RANK_SEVERITY = {
    "C": Severity.MEDIUM,
    "D": Severity.HIGH,
    "E": Severity.HIGH,
    "F": Severity.HIGH,
}


class RadonTool(Tier1Tool):
    name: str = "radon"

    def is_available(self) -> bool:
        return self._check_binary("radon")

    def is_applicable(self, file_path: str) -> bool:
        return file_path.endswith(".py")

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        rc, stdout, stderr = self._run_command(
            ["radon", "cc", "-j", file_path],
            cwd=repo_path,
        )
        if not stdout.strip():
            return []
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("radon: failed to parse JSON output for %s", file_path)
            return []

        findings: list[Finding] = []
        for filepath, blocks in data.items():
            for block in blocks:
                rank = block.get("rank", "A").upper()
                if rank in ("A", "B"):
                    continue
                severity = _RANK_SEVERITY.get(rank, Severity.MEDIUM)
                name = block.get("name", "unknown")
                complexity = block.get("complexity", 0)
                start_line = block.get("lineno", 1)
                end_line = block.get("endline", start_line)
                findings.append(
                    FindingFactory.create_from_tool(
                        tool_name=self.name,
                        file=filepath,
                        start_line=start_line,
                        end_line=end_line,
                        severity=severity,
                        category=FindingCategory.DESIGN,
                        title=f"High complexity in '{name}' (rank {rank}, CC={complexity})",
                        explanation=(
                            f"Function/method '{name}' has cyclomatic complexity "
                            f"{complexity} (rank {rank}). Consider refactoring."
                        ),
                        recommendation="Break the function into smaller, simpler units.",
                    )
                )
        return findings
