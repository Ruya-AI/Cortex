from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class QABridge:
    """Bridge between web UI and existing QA Platform.

    This is the ONLY connection point. It imports from qa_platform
    and calls ScanOrchestrator.scan() exactly like cli/run.py does.
    """

    def run_scan(
        self,
        repo_url: str,
        branch: str | None = None,
        pr_number: int | None = None,
        tiers: list[int] | None = None,
        cost_limit: float | None = None,
        progress_callback=None,
    ) -> dict:
        """Run a QA scan using the existing platform.

        Returns a dict with scan results (not ScanResult dataclass,
        to avoid coupling web layer to QA platform internals).
        """
        import sys
        print(f"[BRIDGE] run_scan started, repo={repo_url}", flush=True, file=sys.stderr)
        from qa_platform.core.schemas import ScanRequest
        from qa_platform.cli.run import _build_orchestrator
        print(f"[BRIDGE] Imports done, building request...", flush=True, file=sys.stderr)

        request = ScanRequest(
            repo=repo_url,
            branch=branch,
            tiers=tiers or [1, 2],
            trigger="web-ui",
            report_formats=["json", "pdf"],
            pr_number=pr_number,
            cost_limit=cost_limit,
            full_scan=pr_number is None,
        )

        print(f"[BRIDGE] Building orchestrator...", flush=True, file=sys.stderr)
        orchestrator = _build_orchestrator(request)
        print(f"[BRIDGE] Orchestrator built, starting scan...", flush=True, file=sys.stderr)

        log_lines = []

        def capture_progress(msg: str):
            log_lines.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
            if progress_callback:
                progress_callback(msg)

        result = orchestrator.scan(request, progress=capture_progress)

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
