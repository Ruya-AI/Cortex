from __future__ import annotations

import logging
import re
from pathlib import Path

from cortex_engine.core.finding import Confidence, Finding, FindingCategory, Severity
from cortex_engine.core.finding_factory import FindingFactory
from cortex_engine.tools.base import Tier1Tool

logger = logging.getLogger(__name__)

_APPLICABLE_EXTENSIONS = frozenset((".py", ".js", ".ts"))

# Each pattern: (compiled_regex, title, explanation, recommendation, severity)
_PATTERNS: list[tuple[re.Pattern[str], str, str, str, Severity]] = [
    (
        re.compile(r"\beval\s*\("),
        "Use of eval()",
        "eval() executes arbitrary code and can lead to code injection vulnerabilities.",
        "Replace eval() with a safer alternative such as ast.literal_eval() or explicit parsing.",
        Severity.HIGH,
    ),
    (
        re.compile(r"\bexec\s*\("),
        "Use of exec()",
        "exec() executes arbitrary code strings and is a code injection risk.",
        "Avoid exec(); use safer alternatives for dynamic code execution.",
        Severity.HIGH,
    ),
    (
        re.compile(r"subprocess\.[a-zA-Z]+\(.*shell\s*=\s*True"),
        "subprocess with shell=True",
        "Using shell=True with subprocess can allow shell injection attacks.",
        "Use shell=False (the default) and pass arguments as a list.",
        Severity.HIGH,
    ),
    (
        re.compile(r"\bpickle\.loads?\s*\("),
        "Use of pickle.load/loads",
        "Deserializing untrusted data with pickle can lead to arbitrary code execution.",
        "Use a safer serialization format such as JSON, or validate the data source.",
        Severity.HIGH,
    ),
    (
        re.compile(r"\byaml\.load\s*\((?!.*Loader\s*=\s*yaml\.SafeLoader)"),
        "yaml.load without SafeLoader",
        "yaml.load() without SafeLoader can execute arbitrary Python objects.",
        "Use yaml.safe_load() or pass Loader=yaml.SafeLoader explicitly.",
        Severity.MEDIUM,
    ),
    (
        re.compile(
            r"""(?:password|passwd|secret|api_key|apikey|token)\s*=\s*["'][^"']{4,}["']""",
            re.IGNORECASE,
        ),
        "Possible hardcoded secret",
        "A string that looks like a hardcoded password or secret was detected.",
        "Move secrets to environment variables or a secrets manager.",
        Severity.CRITICAL,
    ),
]


class SecurityPatternsTool(Tier1Tool):
    name: str = "security-patterns"

    def is_available(self) -> bool:
        return True

    def is_applicable(self, file_path: str) -> bool:
        return Path(file_path).suffix in _APPLICABLE_EXTENSIONS

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        full_path = repo_path / file_path
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning("security-patterns: cannot read %s: %s", file_path, e)
            return []

        findings: list[Finding] = []
        lines = content.splitlines()
        for line_no, line in enumerate(lines, start=1):
            for pattern, title, explanation, recommendation, severity in _PATTERNS:
                if pattern.search(line):
                    findings.append(
                        FindingFactory.create_from_tool(
                            tool_name=self.name,
                            file=file_path,
                            start_line=line_no,
                            end_line=line_no,
                            severity=severity,
                            category=FindingCategory.SECURITY,
                            title=title,
                            explanation=explanation,
                            recommendation=recommendation,
                            confidence=Confidence.LIKELY,
                        )
                    )
        return findings
