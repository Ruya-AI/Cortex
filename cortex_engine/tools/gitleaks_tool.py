from __future__ import annotations

import json
import logging
from pathlib import Path

from cortex_engine.core.finding import Finding, FindingCategory, Severity
from cortex_engine.core.finding_factory import FindingFactory
from cortex_engine.tools.base import Tier1Tool

logger = logging.getLogger(__name__)


class GitleaksTool(Tier1Tool):
    name: str = "gitleaks"

    def is_available(self) -> bool:
        return self._check_binary("gitleaks")

    def is_applicable(self, file_path: str) -> bool:
        return True

    def run(self, file_path: str, repo_path: Path) -> list[Finding]:
        rc, stdout, stderr = self._run_command(
            [
                "gitleaks",
                "detect",
                f"--source={repo_path}",
                "--report-format=json",
                "--report-path=/dev/stdout",
                "--no-git",
            ],
            cwd=repo_path,
        )
        if not stdout.strip():
            return []
        try:
            items = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("gitleaks: failed to parse JSON output")
            return []

        if not isinstance(items, list):
            return []

        findings: list[Finding] = []
        for item in items:
            leak_file = item.get("File", "")
            # Only report findings for the requested file
            if file_path and not leak_file.endswith(file_path.lstrip("./")):
                continue
            start_line = item.get("StartLine", 1)
            end_line = item.get("EndLine", start_line)
            description = item.get("Description", "Potential secret detected")
            rule_id = item.get("RuleID", "unknown")
            findings.append(
                FindingFactory.create_from_tool(
                    tool_name=self.name,
                    file=leak_file or file_path,
                    start_line=start_line,
                    end_line=end_line,
                    severity=Severity.CRITICAL,
                    category=FindingCategory.SECURITY,
                    title=f"[{rule_id}] {description}",
                    explanation=f"Gitleaks detected a potential secret: {description}.",
                    recommendation="Remove the secret and rotate any exposed credentials.",
                )
            )
        return findings
