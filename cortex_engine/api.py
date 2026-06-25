"""Cortex Engine Public API.

This module is the ONLY interface that external consumers (cortex_backend,
CI/CD pipelines, scripts) should use to interact with the QA engine.

Usage:
    from cortex_engine.api import create_scan_request, run_scan

    request = create_scan_request(repo="https://github.com/org/repo.git", tiers=[1, 2])
    result = run_scan(request, progress=print)

    # With explicit LLM config (no env vars needed):
    llm_config = LLMConfig(provider="vertex_ai", vertex_project_id="my-project")
    result = run_scan(request, progress=print, llm_config=llm_config)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from cortex_engine.core.schemas import ScanRequest, ScanResult

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """LLM provider configuration passed to the engine."""
    provider: str = "vertex_ai"
    api_key: str = ""
    primary_model: str = "claude-opus-4-6"
    fallback_model: str = "claude-sonnet-4-6"
    vertex_project_id: str = ""
    vertex_region: str = "global"
    max_retries: int = 3


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


def create_orchestrator(request: ScanRequest, llm_config: LLMConfig | None = None):
    """Build a fully-wired ScanOrchestrator from a ScanRequest."""
    from cortex_engine.cli.run import _build_orchestrator
    return _build_orchestrator(request, llm_config=llm_config)


def run_scan(
    request: ScanRequest,
    progress: Callable[[str], None] | None = None,
    llm_config: LLMConfig | None = None,
) -> ScanResult:
    """Execute a complete QA scan and return the result.

    Args:
        request: Scan configuration (repo, tiers, etc.)
        progress: Optional callback for progress messages
        llm_config: Optional LLM provider config. If None, reads from env vars.

    Returns:
        ScanResult with findings, report paths, gate status, etc.
    """
    orchestrator = create_orchestrator(request, llm_config=llm_config)
    try:
        return orchestrator.scan(request, progress=progress)
    finally:
        if orchestrator._db_conn is not None:
            try:
                orchestrator._db_conn.close()
            except Exception:
                pass
