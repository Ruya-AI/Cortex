from __future__ import annotations

import json
import logging
from pathlib import Path

from cortex_engine.core.finding import Finding, FindingCategory, Severity
from cortex_engine.core.finding_factory import FindingFactory
from cortex_engine.tools.base import Tier1Tool

logger = logging.getLogger(__name__)


class MarkdownlintTool(Tier1Tool):
    name: str = "markdownlint"

    def is_available(self) -> bool:
        return self._check_binary("markdownlint")

    def is_applicable(self, file_path: str) -> bool:
        return file_path.endswith(".md")

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        rc, stdout, stderr = self._run_command(
            ["markdownlint", file_path, "--json"], cwd=repo_path,
        )
        # markdownlint outputs JSON to stderr
        output = stderr.strip()
        if not output:
            return []
        try:
            items = json.loads(output)
        except json.JSONDecodeError:
            logger.warning("markdownlint: failed to parse JSON for %s", file_path)
            return []
        findings: list[Finding] = []
        for item in items:
            line = item.get("lineNumber", 1)
            rule_names = item.get("ruleNames", [])
            rule = rule_names[0] if rule_names else "unknown"
            desc = item.get("ruleDescription", "")
            findings.append(FindingFactory.create_from_tool(
                tool_name=self.name, file=file_path,
                start_line=line, end_line=line, severity=Severity.LOW,
                category=FindingCategory.DESIGN,
                title=f"[{rule}] {desc}",
                explanation=desc,
                recommendation=f"Fix markdownlint rule {rule}.",
            ))
        return findings
