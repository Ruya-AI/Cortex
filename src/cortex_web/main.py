from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from cortex_web.api.admin import router as admin_router
from cortex_web.api.analytics import router as analytics_router
from cortex_web.api.automation import router as automation_router
from cortex_web.api.github import router as github_router
from cortex_web.api.health import router as health_router
from cortex_web.api.linear import router as linear_router
from cortex_web.api.pull_requests import router as pr_router
from cortex_web.api.qa_execution import router as qa_router
from cortex_web.api.reports import router as reports_router
from cortex_web.api.webhooks import router as webhooks_router
from cortex_web.api.ws import router as ws_router
from cortex_web.config import settings

logger = logging.getLogger(__name__)

_background_tasks: list[asyncio.Task] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Cortex Web...")
    try:
        from cortex_web.database import init_db
        await init_db()
        logger.info("Database initialized")

        from cortex_web.database import async_session
        from sqlalchemy import update
        from cortex_web.models.qa_execution import QAExecution
        from datetime import datetime
        async with async_session() as db:
            result = await db.execute(
                update(QAExecution)
                .where(QAExecution.status.in_(["running", "pending"]))
                .values(status="failed", error_message="Server restarted during scan", completed_at=datetime.utcnow())
            )
            if result.rowcount > 0:
                await db.commit()
                logger.info("Marked %d stale running executions as failed", result.rowcount)
    except Exception as e:
        logger.warning("Database init failed (PostgreSQL may not be running): %s", e)

    # Start scheduled PR fetch loop
    if settings.enable_github:
        from cortex_web.tasks.pr_fetch import scheduled_pr_fetch_loop
        task = asyncio.create_task(scheduled_pr_fetch_loop(interval_seconds=300))
        _background_tasks.append(task)
        logger.info("Scheduled PR fetch loop started (every 300s)")

    # Start stale execution reaper
    reaper_task = asyncio.create_task(_stale_execution_reaper())
    _background_tasks.append(reaper_task)
    logger.info("Stale execution reaper started")

    yield

    # Cancel background tasks on shutdown
    for task in _background_tasks:
        task.cancel()
    _background_tasks.clear()
    logger.info("Shutting down Cortex Web...")


async def _stale_execution_reaper():
    """Periodically check for stale running executions and mark them failed."""
    from cortex_web.database import async_session
    from cortex_web.models.qa_execution import QAExecution
    from cortex_web.services.admin_settings import AdminSettings
    from sqlalchemy import select
    from datetime import datetime, timedelta

    while True:
        await asyncio.sleep(120)
        try:
            async with async_session() as db:
                timeout_minutes = int(await AdminSettings.get(db, "qa.stale_execution_timeout_minutes", "60"))
                cutoff = datetime.utcnow() - timedelta(minutes=timeout_minutes)
                result = await db.execute(
                    select(QAExecution).where(
                        QAExecution.status.in_(["running", "pending"]),
                        QAExecution.created_at < cutoff,
                    )
                )
                stale = result.scalars().all()
                if stale:
                    for ex in stale:
                        ex.status = "failed"
                        ex.error_message = f"Execution timed out — exceeded {timeout_minutes} minute limit"
                        ex.completed_at = datetime.utcnow()
                    await db.commit()
                    logger.info("Stale reaper: marked %d executions as failed (timeout=%dm)", len(stale), timeout_minutes)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("Stale reaper error: %s", e)


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
app.include_router(github_router)
app.include_router(pr_router)
app.include_router(qa_router)
app.include_router(reports_router)
app.include_router(admin_router)
app.include_router(webhooks_router)
app.include_router(ws_router)
app.include_router(linear_router)
app.include_router(automation_router)
app.include_router(analytics_router)

frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
