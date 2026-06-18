from __future__ import annotations

import logging
import re
from pathlib import Path

from qa_platform.core.finding import Confidence, Finding, FindingCategory, Severity
from qa_platform.core.finding_factory import FindingFactory
from qa_platform.tools.base import Tier1Tool

logger = logging.getLogger(__name__)

_RELATIVE_IMPORT_RE = re.compile(
    r"^from\s+(\.+\w*(?:\.\w+)*)\s+import\s+(.+)", re.MULTILINE
)


class CallGraphTool(Tier1Tool):
    name: str = "call-graph"

    def is_available(self) -> bool:
        return True

    def is_applicable(self, file_path: str) -> bool:
        return Path(file_path).suffix == ".py"

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        full_path = repo_path / file_path
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning("call-graph: cannot read %s: %s", file_path, e)
            return []

        findings: list[Finding] = []
        current_module = Path(file_path).stem
        current_package = full_path.parent

        for match in _RELATIVE_IMPORT_RE.finditer(content):
            rel_path = match.group(1)
            # Resolve the relative import to a file path
            dots = len(rel_path) - len(rel_path.lstrip("."))
            module_part = rel_path.lstrip(".")
            target_dir = current_package
            for _ in range(dots - 1):
                target_dir = target_dir.parent
            if module_part:
                target_file = target_dir / (module_part.replace(".", "/") + ".py")
            else:
                continue

            if not target_file.is_file():
                continue

            # Check if target file imports back from current module
            try:
                target_content = target_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            # Look for an import of the current module name in the target
            back_import_re = re.compile(
                rf"(?:^from\s+\S*\s+import\s+.*\b{re.escape(current_module)}\b"
                rf"|^import\s+\S*\.{re.escape(current_module)}\b)",
                re.MULTILINE,
            )
            if back_import_re.search(target_content):
                line_no = content[: match.start()].count("\n") + 1
                findings.append(
                    FindingFactory.create_from_tool(
                        tool_name=self.name,
                        file=file_path,
                        start_line=line_no,
                        end_line=line_no,
                        severity=Severity.MEDIUM,
                        category=FindingCategory.DESIGN,
                        title=f"Potential circular import with {target_file.name}",
                        explanation=(
                            f"This module imports from {module_part} which in turn "
                            f"imports from {current_module}, creating a circular dependency."
                        ),
                        recommendation="Break the cycle by moving shared code to a separate module.",
                        confidence=Confidence.UNCERTAIN,
                    )
                )

        return findings
