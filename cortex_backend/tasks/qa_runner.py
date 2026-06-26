from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from cortex_backend.database import async_session
from cortex_backend.models.pull_request import PullRequest
from cortex_backend.models.qa_execution import QAExecution
from cortex_backend.models.qa_finding import QAFinding
from cortex_backend.services.engine_bridge import EngineBridge

logger = logging.getLogger(__name__)


async def run_qa_for_pr(
    pull_request_id: str,
    tiers: list[int] | None = None,
    cost_limit: float | None = None,
):
    """Run QA scan for a specific PR and store results."""
    async with async_session() as db:
        pr_result = await db.execute(select(PullRequest).where(PullRequest.id == pull_request_id))
        pr = pr_result.scalar_one_or_none()
        if not pr:
            logger.error("PR not found: %s", pull_request_id)
            return

        # Create execution record
        execution = QAExecution(
            id=str(uuid.uuid4()),
            pull_request_id=pull_request_id,
            repository_url=f"https://github.com/{pr.owner}/{pr.repo_name}.git",
            branch=pr.source_branch,
            commit_sha="",
            tiers=",".join(str(t) for t in (tiers or [1, 2])),
            trigger="web-ui",
            status="running",
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(execution)

        # Update PR status
        pr.qa_status = "running"
        pr.last_qa_execution_id = execution.id
        await db.commit()

        # Run QA via bridge
        try:
            bridge = EngineBridge()
            progress_lines: list[str] = []

            def on_progress(msg: str):
                progress_lines.append(msg)
                # In production, broadcast via WebSocket:
                # asyncio.create_task(broadcast_progress(execution.id, {"type": "progress", "message": msg}))

            scan_result = await bridge.run_scan_async(
                repo_url=f"https://github.com/{pr.owner}/{pr.repo_name}.git",
                branch=pr.source_branch,
                pr_number=pr.github_pr_number,
                tiers=tiers or [1, 2],
                cost_limit=cost_limit,
                progress_callback=on_progress,
            )

            # Update execution
            execution.status = "completed"
            execution.scan_id = scan_result.get("scan_id", "")
            execution.finding_count = scan_result.get("finding_count", 0)
            execution.severity_counts = scan_result.get("severity_counts")
            execution.quality_gate_status = scan_result.get("quality_gate_status", "")
            execution.duration_seconds = scan_result.get("execution_duration", 0.0)
            execution.cost_usd = scan_result.get("execution_cost", 0.0)
            execution.report_json_path = scan_result.get("json_path", "")
            execution.report_pdf_path = scan_result.get("pdf_path", "")
            execution.executive_json_path = scan_result.get("executive_json_path", "")
            execution.executive_pdf_path = scan_result.get("executive_pdf_path", "")
            execution.execution_log = "\n".join(progress_lines)

            if scan_result.get("errors"):
                execution.error_message = "\n".join(scan_result["errors"])

            # Store findings
            if scan_result.get("json_path"):
                try:
                    report_data = json.loads(Path(scan_result["json_path"]).read_text())
                    for finding in report_data.get("findings", [])[:200]:  # Cap at 200
                        sev = finding.get("severity", "info")
                        if isinstance(sev, int):
                            sev = {4: "critical", 3: "high", 2: "medium", 1: "low", 0: "info"}.get(sev, "info")
                        qa_finding = QAFinding(
                            id=str(uuid.uuid4()),
                            execution_id=execution.id,
                            finding_id=finding.get("id", ""),
                            source=finding.get("source", ""),
                            tier=finding.get("tier", 1),
                            category=finding.get("category", "unknown"),
                            severity=sev,
                            confidence=str(finding.get("confidence", "likely")),
                            file_path=finding.get("file", ""),
                            start_line=finding.get("start_line", 0),
                            end_line=finding.get("end_line", 0),
                            title=finding.get("title", ""),
                            explanation=finding.get("explanation", "")[:2000],
                            recommendation=finding.get("recommendation", "")[:2000],
                            cwe=finding.get("cwe"),
                            validation_status=str(finding.get("validation_status", "unvalidated")),
                        )
                        db.add(qa_finding)
                except Exception as e:
                    logger.warning("Failed to store findings: %s", e)

            # Update PR status
            pr.qa_status = "completed"

        except Exception as e:
            logger.error("QA execution failed for PR %s: %s", pull_request_id, e)
            execution.status = "failed"
            execution.error_message = str(e)
            pr.qa_status = "failed"

        finally:
            execution.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.commit()


async def run_qa_for_multiple_prs(pr_ids: list[str], tiers: list[int] | None = None):
    """Run QA for multiple PRs sequentially."""
    for pr_id in pr_ids:
        await run_qa_for_pr(pr_id, tiers=tiers)
