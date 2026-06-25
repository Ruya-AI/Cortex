"""Bridge between cortex_backend and cortex_engine.

This is the ONLY connection point between the backend service layer
and the QA engine. It imports exclusively from cortex_engine.api
(the engine's public interface).
"""
from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class EngineBridge:
    """Execute QA scans via cortex_engine's public API."""

    def run_scan(
        self,
        repo_url: str,
        branch: str | None = None,
        pr_number: int | None = None,
        tiers: list[int] | None = None,
        cost_limit: float | None = None,
        progress_callback=None,
        llm_config=None,
    ) -> dict:
        from cortex_engine.api import create_scan_request, run_scan, LLMConfig

        request = create_scan_request(
            repo=repo_url,
            branch=branch,
            tiers=tiers or [1, 2],
            pr_number=pr_number,
            cost_limit=cost_limit,
            full_scan=pr_number is None,
            trigger="web-ui",
        )

        log_lines: list[str] = []

        def capture_progress(msg: str):
            log_lines.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
            if progress_callback:
                progress_callback(msg)

        result = run_scan(request, progress=capture_progress, llm_config=llm_config)

        return {
            "scan_id": result.report_id,
            "finding_count": result.finding_count,
            "severity_counts": result.severity_counts,
            "quality_gate_status": result.quality_gate_status,
            "execution_duration": result.execution_duration,
            "execution_cost": result.execution_cost,
            "json_path": str(result.json_path) if result.json_path else "",
            "pdf_path": str(result.pdf_path) if result.pdf_path else "",
            "executive_json_path": str(result.executive_json_path) if result.executive_json_path else "",
            "executive_pdf_path": str(result.executive_pdf_path) if result.executive_pdf_path else "",
            "errors": result.errors,
            "log": "\n".join(log_lines),
        }

    async def run_scan_async(self, **kwargs) -> dict:
        """Run scan in a thread pool to not block the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.run_scan(**kwargs))
