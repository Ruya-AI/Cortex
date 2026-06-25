from __future__ import annotations

import logging
from pathlib import Path

from cortex_engine.core.finding import Finding, FindingCategory, Severity
from cortex_engine.core.finding_factory import FindingFactory
from cortex_engine.tools.base import Tier1Tool

logger = logging.getLogger(__name__)

_APPLICABLE_SUFFIXES = {".js", ".ts", ".tsx", ".jsx", ".css", ".scss", ".json", ".md"}


class PrettierTool(Tier1Tool):
    name: str = "prettier"

    def is_available(self) -> bool:
        return self._check_binary("prettier")

    def is_applicable(self, file_path: str) -> bool:
        return Path(file_path).suffix in _APPLICABLE_SUFFIXES

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        try:
            rc, stdout, stderr = self._run_command(
                ["prettier", "--check", file_path],
                cwd=repo_path,
            )
        except Exception:
            logger.warning("prettier: unexpected error running on %s", file_path)
            return []

        if rc == 0:
            return []

        return [
            FindingFactory.create_from_tool(
                tool_name=self.name,
                file=file_path,
                start_line=1,
                end_line=1,
                severity=Severity.LOW,
                category=FindingCategory.DESIGN,
                title="File is not formatted according to Prettier",
                explanation="Prettier --check reported this file does not match expected formatting.",
                recommendation="Run `prettier --write` on this file to fix formatting.",
            )
        ]
