from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex_backend.database import get_db
from cortex_backend.models.automation_rule import AutomationRule

router = APIRouter(prefix="/api/automation", tags=["automation"])


class AutomationRuleCreate(BaseModel):
    name: str
    description: str = ""
    trigger_on: str = "pr_opened"
    repository_config_id: str | None = None
    qa_tiers: str = "1,2"
    create_linear_tasks: bool = False
    post_github_comment: bool = True
    min_severity_for_linear: str = "medium"
    schedule_cron: str = ""


@router.get("/rules")
async def list_rules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AutomationRule).order_by(AutomationRule.created_at.desc()))
    rules = result.scalars().all()
    return {"items": [
        {"id": r.id, "name": r.name, "description": r.description,
         "trigger_on": r.trigger_on, "repository_config_id": r.repository_config_id,
         "qa_tiers": r.qa_tiers, "create_linear_tasks": r.create_linear_tasks,
         "post_github_comment": r.post_github_comment,
         "min_severity_for_linear": r.min_severity_for_linear,
         "schedule_cron": r.schedule_cron, "is_active": r.is_active}
        for r in rules
    ]}


@router.post("/rules")
async def create_rule(data: AutomationRuleCreate, db: AsyncSession = Depends(get_db)):
    rule = AutomationRule(
        id=str(uuid.uuid4()),
        name=data.name,
        description=data.description,
        trigger_on=data.trigger_on,
        repository_config_id=data.repository_config_id,
        qa_tiers=data.qa_tiers,
        create_linear_tasks=data.create_linear_tasks,
        post_github_comment=data.post_github_comment,
        min_severity_for_linear=data.min_severity_for_linear,
        schedule_cron=data.schedule_cron,
    )
    db.add(rule)
    await db.commit()
    return {"id": rule.id, "status": "created"}


@router.put("/rules/{rule_id}/toggle")
async def toggle_rule(rule_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AutomationRule).where(AutomationRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.is_active = not rule.is_active
    await db.commit()
    return {"id": rule_id, "is_active": rule.is_active}


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AutomationRule).where(AutomationRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    await db.commit()
    return {"status": "deleted"}
