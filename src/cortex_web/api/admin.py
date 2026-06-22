from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex_web.config import settings
from cortex_web.database import get_db
from cortex_web.models.app_config import AppConfig
from cortex_web.models.github_config import GitHubConfig
from cortex_web.models.linear_config import LinearConfig
from cortex_web.models.automation_rule import AutomationRule

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Get all platform settings."""
    result = await db.execute(select(AppConfig).order_by(AppConfig.category, AppConfig.key))
    configs = result.scalars().all()

    # Count integrations
    gh_result = await db.execute(select(GitHubConfig).where(GitHubConfig.is_active == True))  # noqa: E712
    gh_count = len(gh_result.scalars().all())

    linear_result = await db.execute(select(LinearConfig).where(LinearConfig.is_active == True))  # noqa: E712
    linear_count = len(linear_result.scalars().all())

    rules_result = await db.execute(select(AutomationRule).where(AutomationRule.is_active == True))  # noqa: E712
    rules_count = len(rules_result.scalars().all())

    return {
        "items": [
            {"key": c.key, "value": c.value, "category": c.category, "description": c.description}
            for c in configs
        ],
        "features": {
            "github": settings.enable_github,
            "linear": settings.enable_linear,
            "automation": settings.enable_automation,
            "analytics": settings.enable_analytics,
        },
        "integrations": {
            "github_configs": gh_count,
            "linear_configs": linear_count,
            "automation_rules": rules_count,
        },
    }


class SettingUpdate(BaseModel):
    value: str


@router.put("/settings/{key}")
async def update_setting(key: str, data: SettingUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppConfig).where(AppConfig.key == key))
    config = result.scalar_one_or_none()
    if config:
        config.value = data.value
    else:
        config = AppConfig(key=key, value=data.value)
        db.add(config)
    await db.commit()
    return {"key": key, "value": data.value, "status": "updated"}


@router.get("/system-info")
async def system_info():
    """Get system information including QA platform version."""
    info = {
        "web_version": "1.0.0",
        "features_enabled": {
            "github": settings.enable_github,
            "linear": settings.enable_linear,
            "automation": settings.enable_automation,
            "analytics": settings.enable_analytics,
        },
    }
    try:
        from qa_platform import __version__ as qa_version
        info["qa_platform_version"] = qa_version
    except ImportError:
        info["qa_platform_version"] = "unknown"
    return info
