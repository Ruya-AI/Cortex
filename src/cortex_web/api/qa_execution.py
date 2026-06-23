from __future__ import annotations
import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from cortex_web.database import get_db
from cortex_web.models.qa_execution import QAExecution
from cortex_web.services.qa_bridge import QABridge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/qa", tags=["qa-execution"])

class QAExecutionRequest(BaseModel):
    repository_url: str
    branch: str | None = None
    pr_number: int | None = None
    commit_sha: str | None = None
    tiers: list[int] = [1, 2]
    cost_limit: float | None = None
    execution_type: str = "repository"

@router.post("/execute")
async def trigger_qa_execution(
    request: QAExecutionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    branch = request.commit_sha or request.branch or ""
    execution = QAExecution(
        id=str(uuid.uuid4()),
        repository_url=request.repository_url,
        branch=branch,
        commit_sha=request.commit_sha or "",
        tiers=",".join(str(t) for t in request.tiers),
        execution_type=request.execution_type,
        trigger="web-ui",
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.add(execution)
    await db.commit()

    background_tasks.add_task(
        _run_qa_in_background,
        execution_id=execution.id,
        repo_url=request.repository_url,
        branch=branch or None,
        pr_number=request.pr_number,
        tiers=request.tiers,
        cost_limit=request.cost_limit,
    )

    return {"execution_id": execution.id, "status": "pending"}

@router.get("/executions")
async def list_executions(
    limit: int = 20,
    type: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(QAExecution)
    if type and type in ("repository", "pull_request", "commit"):
        query = query.where(QAExecution.execution_type == type)
    if status and status in ("pending", "running", "completed", "failed"):
        query = query.where(QAExecution.status == status)
    result = await db.execute(query.order_by(QAExecution.created_at.desc()).limit(limit))
    executions = result.scalars().all()
    return {"items": [_exec_to_dict(e) for e in executions]}

@router.get("/executions/{execution_id}")
async def get_execution(execution_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(QAExecution).where(QAExecution.id == execution_id))
    execution = result.scalar_one_or_none()
    if not execution:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Execution not found")
    return _exec_to_dict(execution)

async def _run_qa_in_background(execution_id, repo_url, branch, pr_number, tiers, cost_limit):
    """Run QA scan in background and update the execution record."""
    import asyncio
    from cortex_web.database import async_session
    from cortex_web.api.ws import broadcast_progress

    loop = asyncio.get_running_loop()

    def on_progress(message: str):
        logger.info("QA progress [%s]: %s", execution_id[:8], message)
        fut = asyncio.run_coroutine_threadsafe(
            broadcast_progress(execution_id, {"type": "progress", "message": message, "repository_url": repo_url}),
            loop,
        )
        try:
            fut.result(timeout=5)
        except Exception:
            pass

    async with async_session() as db:
        result = await db.execute(select(QAExecution).where(QAExecution.id == execution_id))
        execution = result.scalar_one_or_none()
        if not execution:
            return

        execution.status = "running"
        execution.started_at = datetime.utcnow()
        await db.commit()

        await broadcast_progress(execution_id, {
            "type": "status", "status": "running", "repository_url": repo_url,
        })

        try:
            bridge = QABridge()
            scan_result = await bridge.run_scan_async(
                repo_url=repo_url,
                branch=branch,
                pr_number=pr_number,
                tiers=tiers,
                cost_limit=cost_limit,
                progress_callback=on_progress,
            )

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
            execution.execution_log = scan_result.get("log", "")
            if scan_result.get("errors"):
                execution.error_message = "\n".join(scan_result["errors"])

            await broadcast_progress(execution_id, {
                "type": "status", "status": "completed", "repository_url": repo_url,
                "finding_count": execution.finding_count,
                "quality_gate_status": execution.quality_gate_status,
                "duration_seconds": execution.duration_seconds,
            })
        except Exception as e:
            execution.status = "failed"
            execution.error_message = str(e)
            await broadcast_progress(execution_id, {
                "type": "status", "status": "failed", "repository_url": repo_url,
                "error": str(e),
            })
        finally:
            execution.completed_at = datetime.utcnow()
            await db.commit()

def _exec_to_dict(e: QAExecution) -> dict:
    return {
        "id": e.id,
        "scan_id": e.scan_id,
        "repository_url": e.repository_url,
        "branch": e.branch,
        "commit_sha": e.commit_sha,
        "tiers": e.tiers,
        "execution_type": e.execution_type,
        "trigger": e.trigger,
        "status": e.status,
        "finding_count": e.finding_count,
        "severity_counts": e.severity_counts,
        "quality_gate_status": e.quality_gate_status,
        "duration_seconds": e.duration_seconds,
        "cost_usd": e.cost_usd,
        "report_json_path": e.report_json_path,
        "executive_json_path": e.executive_json_path,
        "error_message": e.error_message,
        "started_at": e.started_at.isoformat() if e.started_at else None,
        "completed_at": e.completed_at.isoformat() if e.completed_at else None,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }
