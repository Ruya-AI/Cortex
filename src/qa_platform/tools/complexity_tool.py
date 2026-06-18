from __future__ import annotations

import json
import logging
from pathlib import Path

from qa_platform.core.finding import Finding, FindingCategory, Severity
from qa_platform.core.finding_factory import FindingFactory
from qa_platform.tools.base import Tier1Tool

logger = logging.getLogger(__name__)


class ComplexityTool(Tier1Tool):
    name: str = "complexity-analyzer"

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
            logger.warning("complexity-analyzer: failed to parse JSON for %s", file_path)
            return []

        findings: list[Finding] = []
        for filepath, blocks in data.items():
            for block in blocks:
                complexity = block.get("complexity", 0)
                if complexity <= 10:
                    continue
                name = block.get("name", "unknown")
                start_line = block.get("lineno", 1)
                end_line = block.get("endline", start_line)
                rank = block.get("rank", "?")
                if complexity > 20:
                    severity = Severity.HIGH
                else:
                    severity = Severity.MEDIUM
                findings.append(
                    FindingFactory.create_from_tool(
                        tool_name=self.name,
                        file=filepath,
                        start_line=start_line,
                        end_line=end_line,
                        severity=severity,
                        category=FindingCategory.DESIGN,
                        title=f"Excessive complexity in '{name}' (CC={complexity}, rank {rank})",
                        explanation=(
                            f"Function/method '{name}' has cyclomatic complexity "
                            f"{complexity} (rank {rank}), exceeding the threshold of 10. "
                            f"This makes the code harder to test and maintain."
                        ),
                        recommendation=(
                            "Refactor the function by extracting helper methods, "
                            "simplifying conditional logic, or using early returns."
                        ),
                    )
                )
        return findings
