from __future__ import annotations

import logging
import re
from pathlib import Path

from cortex_engine.core.finding import Confidence, Finding, FindingCategory, Severity
from cortex_engine.core.finding_factory import FindingFactory
from cortex_engine.tools.base import Tier1Tool

logger = logging.getLogger(__name__)

# Matches: import X, import X as Y, import X.Y.Z, import X.Y.Z as W
_IMPORT_RE = re.compile(r"^import\s+(\S+)(?:\s+as\s+(\w+))?", re.MULTILINE)

# Matches: from X import A, B, C  (with optional 'as' aliases)
_FROM_IMPORT_RE = re.compile(r"^from\s+\S+\s+import\s+(.+)", re.MULTILINE)

# Splits "A, B as C, D" into individual tokens
_NAME_AS_RE = re.compile(r"(\w+)(?:\s+as\s+(\w+))?")


class UnusedModuleTool(Tier1Tool):
    name: str = "unused-module"

    def is_available(self) -> bool:
        return True

    def is_applicable(self, file_path: str) -> bool:
        p = Path(file_path)
        if p.suffix != ".py":
            return False
        if p.name == "__init__.py":
            return False
        return True

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        full_path = repo_path / file_path
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning("unused-module: cannot read %s: %s", file_path, e)
            return []

        # Skip files that use TYPE_CHECKING-guarded imports entirely is too broad;
        # instead we will skip individual names found only inside TYPE_CHECKING blocks.
        # For simplicity, we skip imports on lines inside an "if TYPE_CHECKING:" block.
        lines = content.splitlines()

        # Collect imported names: list of (name, line_no)
        imported: list[tuple[str, int]] = []

        for match in _IMPORT_RE.finditer(content):
            line_no = content[: match.start()].count("\n") + 1
            # Skip star imports
            if "*" in match.group(0):
                continue
            alias = match.group(2)
            if alias:
                imported.append((alias, line_no))
            else:
                # Use the last segment of a dotted import
                module = match.group(1)
                imported.append((module.split(".")[-1], line_no))

        for match in _FROM_IMPORT_RE.finditer(content):
            line_no = content[: match.start()].count("\n") + 1
            names_str = match.group(1).strip().rstrip("\\").strip("()")
            # Skip star imports
            if "*" in names_str:
                continue
            for name_match in _NAME_AS_RE.finditer(names_str):
                alias = name_match.group(2) or name_match.group(1)
                imported.append((alias, line_no))

        # Check usage: the name must appear somewhere else in the file
        findings: list[Finding] = []
        for name, line_no in imported:
            if not name or len(name) < 2:
                continue
            # Check if the name appears on any line other than its import line
            # Use word-boundary search on the full content minus the import line
            pattern = re.compile(rf"\b{re.escape(name)}\b")
            used = False
            for idx, line in enumerate(lines, start=1):
                if idx == line_no:
                    continue
                if pattern.search(line):
                    used = True
                    break
            if not used:
                findings.append(
                    FindingFactory.create_from_tool(
                        tool_name=self.name,
                        file=file_path,
                        start_line=line_no,
                        end_line=line_no,
                        severity=Severity.LOW,
                        category=FindingCategory.DESIGN,
                        title=f"Unused import: {name}",
                        explanation=(
                            f"'{name}' is imported but never referenced elsewhere in the file."
                        ),
                        recommendation=f"Remove the unused import of '{name}' or add a noqa comment if intentional.",
                        confidence=Confidence.UNCERTAIN,
                    )
                )

        return findings
