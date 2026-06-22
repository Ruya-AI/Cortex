from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from cortex_web.api.admin import router as admin_router
from cortex_web.api.health import router as health_router
from cortex_web.api.pull_requests import router as pr_router
from cortex_web.api.qa_execution import router as qa_router
from cortex_web.api.reports import router as reports_router
from cortex_web.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Cortex Web...")
    try:
        from cortex_web.database import init_db
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning("Database init failed (PostgreSQL may not be running): %s", e)
    yield
    logger.info("Shutting down Cortex Web...")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Cortex QA Platform — Web Extension",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(pr_router)
app.include_router(qa_router)
app.include_router(reports_router)
app.include_router(admin_router)

frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
