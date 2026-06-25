"""Cortex Engine Public API.

This module is the ONLY interface that external consumers (cortex_backend,
CI/CD pipelines, scripts) should use to interact with the QA engine.

Usage:
    from cortex_engine.api import create_scan_request, run_scan, create_orchestrator

    request = create_scan_request(repo="https://github.com/org/repo.git", tiers=[1, 2])
    result = run_scan(request, progress=print)
"""
from __future__ import annotations

import logging
from typing import Callable

from cortex_engine.core.schemas import ScanRequest, ScanResult

logger = logging.getLogger(__name__)


def create_scan_request(
    repo: str,
    branch: str | None = None,
    commit: str | None = None,
    tiers: list[int] | None = None,
    pr_number: int | None = None,
    full_scan: bool = True,
    report_formats: list[str] | None = None,
    cost_limit: float | None = None,
    trigger: str = "api",
) -> ScanRequest:
    """Create a ScanRequest with sensible defaults."""
    return ScanRequest(
        repo=repo,
        branch=branch,
        commit=commit,
        tiers=tiers or [1, 2],
        trigger=trigger,
        report_formats=report_formats or ["json", "pdf"],
        pr_number=pr_number,
        cost_limit=cost_limit,
        full_scan=full_scan,
    )


def create_orchestrator(request: ScanRequest):
    """Build a fully-wired ScanOrchestrator from a ScanRequest.

    This is the composition root — creates and connects all dependencies
    (tools, agents, report generators, etc.) based on the request config.
    """
    from cortex_engine.cli.run import _build_orchestrator
    return _build_orchestrator(request)


def run_scan(
    request: ScanRequest,
    progress: Callable[[str], None] | None = None,
) -> ScanResult:
    """Execute a complete QA scan and return the result.

    This is the simplest way to run the engine. Creates an orchestrator,
    runs the scan, and returns the result. The orchestrator is cleaned up
    after the scan completes.

    Args:
        request: Scan configuration (repo, tiers, etc.)
        progress: Optional callback for progress messages

    Returns:
        ScanResult with findings, report paths, gate status, etc.
    """
    orchestrator = create_orchestrator(request)
    try:
        return orchestrator.scan(request, progress=progress)
    finally:
        if orchestrator._db_conn is not None:
            try:
                orchestrator._db_conn.close()
            except Exception:
                pass
