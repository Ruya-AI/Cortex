from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy import select

from cortex_web.database import async_session
from cortex_web.models.linear_task import LinearTask
from cortex_web.models.qa_finding import QAFinding
from cortex_web.services.admin_settings import AdminSettings

logger = logging.getLogger(__name__)


async def create_linear_tasks_for_execution(execution_id: str):
    """Create Linear tasks for findings from a QA execution."""
    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}

    async with async_session() as db:
        # Get Linear config from admin settings
        api_key = await AdminSettings.get(db, "linear.api_key")
        if not api_key:
            logger.info("No Linear API key configured in admin settings — skipping task creation")
            return

        min_severity = await AdminSettings.get(db, "linear.min_severity", "medium")
        max_tasks = int(await AdminSettings.get(db, "linear.max_tasks_per_scan", "20"))
        min_rank = severity_rank.get(min_severity, 2)

        # Get findings above min severity
        findings_result = await db.execute(
            select(QAFinding).where(QAFinding.execution_id == execution_id)
        )
        findings = findings_result.scalars().all()

        eligible = [f for f in findings if severity_rank.get(f.severity, 0) >= min_rank]

        created = 0
        for finding in eligible[:max_tasks]:
            task = LinearTask(
                id=str(uuid.uuid4()),
                execution_id=execution_id,
                finding_id=finding.id,
                linear_issue_id="",  # Set after API call
                title=f"[{finding.severity.upper()}] {finding.title[:100]}",
                status="created",
                priority=finding.severity,
                created_at=datetime.utcnow(),
            )
            db.add(task)

            # Link finding to task
            finding.linear_task_id = task.id
            created += 1

        await db.commit()
        logger.info("Created %d Linear tasks for execution %s", created, execution_id)
