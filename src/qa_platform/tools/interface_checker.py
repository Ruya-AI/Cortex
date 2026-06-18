from __future__ import annotations

import logging
import re
from pathlib import Path

from qa_platform.core.finding import Confidence, Finding, FindingCategory, Severity
from qa_platform.core.finding_factory import FindingFactory
from qa_platform.tools.base import Tier1Tool

logger = logging.getLogger(__name__)

_ABC_CLASS_RE = re.compile(r"^class\s+(\w+)\s*\(([^)]*)\)\s*:", re.MULTILINE)
_ABSTRACT_METHOD_RE = re.compile(r"@abstractmethod\s+def\s+(\w+)", re.MULTILINE)
_TYPE_IGNORE_RE = re.compile(r"#\s*type:\s*ignore")


class InterfaceCheckerTool(Tier1Tool):
    name: str = "interface-checker"

    def is_available(self) -> bool:
        return True

    def is_applicable(self, file_path: str) -> bool:
        return Path(file_path).suffix in (".py", ".ts")

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        try:
            content = (repo_path / file_path).read_text(errors="replace")
        except (OSError, ValueError):
            return []

        if Path(file_path).suffix == ".py":
            return self._check_python(file_path, content)
        return []

    def _check_python(self, file_path: str, content: str) -> list[Finding]:
        findings: list[Finding] = []
        lines = content.splitlines()

        # Find classes and their bases
        classes: dict[str, tuple[int, str]] = {}
        for m in _ABC_CLASS_RE.finditer(content):
            name, bases = m.group(1), m.group(2)
            lineno = content[:m.start()].count("\n") + 1
            classes[name] = (lineno, bases)

        # Check for @abstractmethod in non-ABC classes
        for m in _ABSTRACT_METHOD_RE.finditer(content):
            method_name = m.group(1)
            method_line = content[:m.start()].count("\n") + 1
            # Find the enclosing class
            enclosing_class = None
            for cls_name, (cls_line, cls_bases) in classes.items():
                if cls_line < method_line:
                    enclosing_class = (cls_name, cls_line, cls_bases)
            if enclosing_class:
                cls_name, cls_line, cls_bases = enclosing_class
                has_abc = any(b.strip() in ("ABC", "ABCMeta") for b in cls_bases.split(","))
                if not has_abc:
                    findings.append(
                        FindingFactory.create_from_tool(
                            tool_name=self.name,
                            file=file_path,
                            start_line=method_line,
                            end_line=method_line,
                            severity=Severity.MEDIUM,
                            category=FindingCategory.CORRECTNESS,
                            title=f"@abstractmethod in non-ABC class '{cls_name}'",
                            explanation=f"Method '{method_name}' uses @abstractmethod but class '{cls_name}' does not inherit from ABC.",
                            recommendation=f"Add ABC to the base classes of '{cls_name}'.",
                            confidence=Confidence.UNCERTAIN,
                        )
                    )

        # Flag lines with type: ignore
        for i, line in enumerate(lines, start=1):
            if _TYPE_IGNORE_RE.search(line):
                findings.append(
                    FindingFactory.create_from_tool(
                        tool_name=self.name,
                        file=file_path,
                        start_line=i,
                        end_line=i,
                        severity=Severity.LOW,
                        category=FindingCategory.CORRECTNESS,
                        title="'# type: ignore' suppresses type checking",
                        explanation="A '# type: ignore' comment was found. This may hide real type errors.",
                        recommendation="Verify the type suppression is intentional and add a specific error code.",
                        confidence=Confidence.UNCERTAIN,
                    )
                )

        return findings
