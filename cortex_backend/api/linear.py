from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex_backend.database import get_db
from cortex_backend.models.linear_task import LinearTask

router = APIRouter(prefix="/api/linear", tags=["linear"])


@router.get("/tasks")
async def list_linear_tasks(
    execution_id: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    query = select(LinearTask).order_by(LinearTask.created_at.desc())
    if execution_id:
        query = query.where(LinearTask.execution_id == execution_id)
    query = query.limit(limit)
    result = await db.execute(query)
    tasks = result.scalars().all()
    return {"items": [
        {"id": t.id, "execution_id": t.execution_id, "finding_id": t.finding_id,
         "linear_issue_id": t.linear_issue_id, "linear_issue_url": t.linear_issue_url,
         "linear_issue_identifier": t.linear_issue_identifier, "title": t.title,
         "status": t.status, "assignee": t.assignee, "priority": t.priority,
         "created_at": t.created_at.isoformat()}
        for t in tasks
    ]}


@router.post("/tasks/create-from-execution/{execution_id}")
async def create_tasks_from_execution(execution_id: str):
    from cortex_backend.tasks.linear_sync import create_linear_tasks_for_execution
    await create_linear_tasks_for_execution(execution_id)
    return {"status": "created", "execution_id": execution_id}
