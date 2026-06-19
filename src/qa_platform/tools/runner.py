from __future__ import annotations

import logging
import time
from pathlib import Path

from qa_platform.core.finding import Finding
from qa_platform.core.schemas import Tier1RunResult
from qa_platform.tools.base import Tier1Tool

logger = logging.getLogger(__name__)


class Tier1Runner:
    def __init__(self, tools: list[Tier1Tool] | None = None, max_duration: float = 300.0) -> None:
        self._tools = tools or []
        self._max_duration = max_duration

    def register(self, tool: Tier1Tool) -> None:
        self._tools.append(tool)

    def run(
        self, repo_path: Path, file_paths: list[str], trigger: str,
    ) -> Tier1RunResult:
        start = time.time()
        available: list[Tier1Tool] = []
        skipped: list[str] = []
        for tool in self._tools:
            if tool.is_available():
                available.append(tool)
            else:
                skipped.append(tool.name)
                logger.info("Tool %s not available — skipped", tool.name)

        all_findings: list[Finding] = []
        tool_summary: dict[str, dict] = {}

        for tool in available:
            if time.time() - start > self._max_duration:
                logger.warning("Tier 1 aggregate timeout (%.0fs) — remaining tools skipped", self._max_duration)
                break
            tool_start = time.time()
            try:
                findings = tool.run_batch(file_paths, repo_path)
                all_findings.extend(findings)
                tool_summary[tool.name] = {
                    "finding_count": len(findings),
                    "duration": round(time.time() - tool_start, 2),
                    "status": "success",
                }
            except Exception as e:
                logger.warning("Tool %s failed: %s", tool.name, e)
                tool_summary[tool.name] = {
                    "finding_count": 0,
                    "duration": round(time.time() - tool_start, 2),
                    "status": "error",
                    "error": str(e),
                }

        return Tier1RunResult(
            findings=all_findings,
            tool_summary=tool_summary,
            finding_count=len(all_findings),
            duration_seconds=round(time.time() - start, 2),
            tools_available=[t.name for t in available],
            tools_skipped=skipped,
        )
