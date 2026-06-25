from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from cortex_backend.database import get_db
from cortex_backend.services.analytics import AnalyticsService

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    """Get executive dashboard metrics."""
    service = AnalyticsService()
    return await service.get_executive_dashboard(db)


@router.get("/patterns")
async def get_patterns(db: AsyncSession = Depends(get_db)):
    """Get finding pattern analysis."""
    service = AnalyticsService()
    return await service.get_finding_patterns(db)
