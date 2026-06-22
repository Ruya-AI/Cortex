from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex_web.database import get_db
from cortex_web.models.linear_config import LinearConfig
from cortex_web.models.linear_task import LinearTask

router = APIRouter(prefix="/api/linear", tags=["linear"])


class LinearConfigCreate(BaseModel):
    name: str
    api_key: str
    team_id: str
    workspace_name: str = ""
    auto_create_tasks: bool = False
    min_severity: str = "medium"
    max_tasks_per_scan: int = 20


@router.get("/configs")
async def list_linear_configs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LinearConfig).order_by(LinearConfig.created_at.desc()))
    configs = result.scalars().all()
    return {"items": [
        {"id": c.id, "name": c.name, "team_id": c.team_id, "workspace_name": c.workspace_name,
         "auto_create_tasks": c.auto_create_tasks, "min_severity": c.min_severity,
         "max_tasks_per_scan": c.max_tasks_per_scan, "is_active": c.is_active,
         "created_at": c.created_at.isoformat()}
        for c in configs
    ]}


@router.post("/configs")
async def create_linear_config(data: LinearConfigCreate, db: AsyncSession = Depends(get_db)):
    config = LinearConfig(
        id=str(uuid.uuid4()),
        name=data.name,
        api_key_encrypted=data.api_key,  # In production, encrypt
        team_id=data.team_id,
        workspace_name=data.workspace_name,
        auto_create_tasks=data.auto_create_tasks,
        min_severity=data.min_severity,
        max_tasks_per_scan=data.max_tasks_per_scan,
    )
    db.add(config)
    await db.commit()
    return {"id": config.id, "status": "created"}


@router.delete("/configs/{config_id}")
async def delete_linear_config(config_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LinearConfig).where(LinearConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    await db.delete(config)
    await db.commit()
    return {"status": "deleted"}


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
async def create_tasks_from_execution(execution_id: str, db: AsyncSession = Depends(get_db)):
    """Create Linear tasks from QA findings of an execution."""
    from cortex_web.tasks.linear_sync import create_linear_tasks_for_execution
    await create_linear_tasks_for_execution(execution_id)
    return {"status": "created", "execution_id": execution_id}
