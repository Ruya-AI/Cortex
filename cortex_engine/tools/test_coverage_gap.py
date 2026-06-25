from __future__ import annotations

import logging
from pathlib import Path

from cortex_engine.core.finding import Finding, FindingCategory, Severity
from cortex_engine.core.finding_factory import FindingFactory
from cortex_engine.tools.base import Tier1Tool

logger = logging.getLogger(__name__)


class TestCoverageGapTool(Tier1Tool):
    name: str = "test-coverage-gap"

    def is_available(self) -> bool:
        return True

    def is_applicable(self, file_path: str) -> bool:
        p = Path(file_path)
        if p.suffix != ".py":
            return False
        if p.name.startswith("test_") or p.name.endswith("_test.py"):
            return False
        # Skip files inside test/tests directories
        parts = p.parts
        if "tests" in parts or "test" in parts:
            return False
        return True

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        p = Path(file_path)
        stem = p.stem
        test_prefix = f"test_{p.name}"
        test_suffix = f"{stem}_test.py"

        candidates = [
            # tests/ directory relative to repo root
            repo_path / "tests" / test_prefix,
            repo_path / "tests" / test_suffix,
            # tests/ directory next to the file
            repo_path / p.parent / "tests" / test_prefix,
            repo_path / p.parent / "tests" / test_suffix,
            # Same directory
            repo_path / p.parent / test_prefix,
            repo_path / p.parent / test_suffix,
            # test/ (singular) directory
            repo_path / "test" / test_prefix,
            repo_path / p.parent / "test" / test_prefix,
        ]

        for candidate in candidates:
            if candidate.is_file():
                return []

        return [
            FindingFactory.create_from_tool(
                tool_name=self.name,
                file=file_path,
                start_line=1,
                end_line=1,
                severity=Severity.MEDIUM,
                category=FindingCategory.DESIGN,
                title=f"No test file found for {p.name}",
                explanation=(
                    f"No corresponding test file (test_{p.name} or {test_suffix}) "
                    f"was found in tests/, test/, or the same directory."
                ),
                recommendation=f"Create a test file (e.g. test_{p.name}) with unit tests for this module.",
            )
        ]
