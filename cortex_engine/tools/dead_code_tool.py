from __future__ import annotations

import logging
import re
from pathlib import Path

from cortex_engine.core.finding import Finding, FindingCategory, Severity
from cortex_engine.core.finding_factory import FindingFactory
from cortex_engine.tools.base import Tier1Tool

logger = logging.getLogger(__name__)

_VULTURE_RE = re.compile(r"(\S+):(\d+): (.+) \((\d+)% confidence\)")


class DeadCodeTool(Tier1Tool):
    name: str = "dead-code"

    def is_available(self) -> bool:
        return True

    def is_applicable(self, file_path: str) -> bool:
        return Path(file_path).suffix == ".py"

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        if self._check_binary("vulture"):
            return self._run_vulture(file_path, repo_path)
        return self._run_heuristic(file_path, repo_path)

    def _run_vulture(self, file_path: str, repo_path: Path) -> list[Finding]:
        try:
            rc, stdout, stderr = self._run_command(
                ["vulture", file_path, "--min-confidence", "80"],
                cwd=repo_path,
            )
        except Exception:
            logger.warning("dead-code: vulture failed on %s", file_path)
            return []

        findings: list[Finding] = []
        for line in stdout.splitlines():
            m = _VULTURE_RE.match(line)
            if not m:
                continue
            fpath, lineno, message, confidence = m.group(1), int(m.group(2)), m.group(3), m.group(4)
            findings.append(
                FindingFactory.create_from_tool(
                    tool_name=self.name,
                    file=fpath,
                    start_line=lineno,
                    end_line=lineno,
                    severity=Severity.LOW,
                    category=FindingCategory.DESIGN,
                    title=f"Dead code: {message}",
                    explanation=f"{message} ({confidence}% confidence).",
                    recommendation="Remove unused code or mark it as used.",
                )
            )
        return findings

    def _run_heuristic(self, file_path: str, repo_path: Path) -> list[Finding]:
        try:
            content = (repo_path / file_path).read_text(errors="replace")
        except (OSError, ValueError):
            return []

        lines = content.splitlines()
        def_re = re.compile(r"^\s*(?:def|class)\s+(\w+)")
        definitions: list[tuple[str, int]] = []
        for i, line in enumerate(lines, start=1):
            m = def_re.match(line)
            if m:
                definitions.append((m.group(1), i))

        findings: list[Finding] = []
        for name, lineno in definitions:
            # Count occurrences beyond the definition itself
            count = sum(1 for ln in lines if re.search(r"\b" + re.escape(name) + r"\b", ln))
            if count <= 1:
                findings.append(
                    FindingFactory.create_from_tool(
                        tool_name=self.name,
                        file=file_path,
                        start_line=lineno,
                        end_line=lineno,
                        severity=Severity.LOW,
                        category=FindingCategory.DESIGN,
                        title=f"Possibly unused: '{name}'",
                        explanation=f"'{name}' defined at line {lineno} appears only once in the file.",
                        recommendation="Verify if this code is used elsewhere or remove it.",
                    )
                )
        return findings
