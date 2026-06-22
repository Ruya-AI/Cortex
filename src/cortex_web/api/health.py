from __future__ import annotations
from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "cortex-web", "version": "1.0.0"}

@router.get("/health/qa")
async def qa_health():
    """Check if the QA platform is accessible."""
    try:
        from qa_platform import __version__
        return {"status": "ok", "qa_platform_version": __version__}
    except ImportError:
        return {"status": "error", "message": "QA Platform not found"}
