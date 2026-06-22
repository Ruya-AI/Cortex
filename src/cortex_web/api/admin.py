from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from cortex_web.database import get_db
from cortex_web.models.app_config import AppConfig
from cortex_web.config import settings

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppConfig).order_by(AppConfig.category, AppConfig.key))
    configs = result.scalars().all()
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
    }

@router.put("/settings/{key}")
async def update_setting(key: str, value: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppConfig).where(AppConfig.key == key))
    config = result.scalar_one_or_none()
    if config:
        config.value = value
    else:
        config = AppConfig(key=key, value=value)
        db.add(config)
    await db.commit()
    return {"key": key, "value": value, "status": "updated"}
