from __future__ import annotations

import logging
import re
from pathlib import Path

from cortex_engine.core.finding import Finding, FindingCategory, Severity
from cortex_engine.core.finding_factory import FindingFactory
from cortex_engine.tools.base import Tier1Tool

logger = logging.getLogger(__name__)

_RAW_SQL_RE = re.compile(r"""execute\s*\(\s*(?:f["']|["'][^"']*["']\s*\+|[^)]*\.format\()""")


class MigrationCheckerTool(Tier1Tool):
    name: str = "migration-checker"

    def is_available(self) -> bool:
        return True

    def is_applicable(self, file_path: str) -> bool:
        lower = file_path.lower()
        return "/migration/" in lower or "/migrations/" in lower

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        full_path = repo_path / file_path
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning("migration-checker: cannot read %s: %s", file_path, e)
            return []

        findings: list[Finding] = []

        # Check 1: missing down migration (Python migration files only)
        if Path(file_path).suffix == ".py":
            has_up = "def upgrade" in content or "def forwards" in content
            has_down = "def downgrade" in content or "def backwards" in content
            if has_up and not has_down:
                findings.append(
                    FindingFactory.create_from_tool(
                        tool_name=self.name,
                        file=file_path,
                        start_line=1,
                        end_line=1,
                        severity=Severity.MEDIUM,
                        category=FindingCategory.SECURITY,
                        title="Missing down migration",
                        explanation=(
                            "Migration defines an upgrade/forwards function but no "
                            "corresponding downgrade/backwards function, making rollback impossible."
                        ),
                        recommendation="Add a downgrade() or backwards() function to enable safe rollbacks.",
                    )
                )

        # Check 2: raw SQL without parameterization
        for line_no, line in enumerate(content.splitlines(), start=1):
            if _RAW_SQL_RE.search(line):
                findings.append(
                    FindingFactory.create_from_tool(
                        tool_name=self.name,
                        file=file_path,
                        start_line=line_no,
                        end_line=line_no,
                        severity=Severity.HIGH,
                        category=FindingCategory.SECURITY,
                        title="Raw SQL without parameterization",
                        explanation=(
                            "SQL is constructed via string concatenation or f-strings, "
                            "which risks SQL injection."
                        ),
                        recommendation="Use parameterized queries (e.g. execute(sql, params)) instead.",
                    )
                )

        return findings
