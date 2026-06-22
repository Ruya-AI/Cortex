from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy import select

from cortex_web.database import async_session
from cortex_web.models.linear_config import LinearConfig
from cortex_web.models.linear_task import LinearTask
from cortex_web.models.qa_finding import QAFinding

logger = logging.getLogger(__name__)


async def create_linear_tasks_for_execution(execution_id: str, min_severity: str = "medium"):
    """Create Linear tasks for findings from a QA execution."""
    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
    min_rank = severity_rank.get(min_severity, 2)

    async with async_session() as db:
        # Get active Linear config
        lc_result = await db.execute(
            select(LinearConfig).where(LinearConfig.is_active == True)  # noqa: E712
        )
        linear_config = lc_result.scalar_one_or_none()
        if not linear_config:
            logger.info("No active Linear config — skipping task creation")
            return

        # Get findings above min severity
        findings_result = await db.execute(
            select(QAFinding).where(QAFinding.execution_id == execution_id)
        )
        findings = findings_result.scalars().all()

        eligible = [f for f in findings if severity_rank.get(f.severity, 0) >= min_rank]
        max_tasks = linear_config.max_tasks_per_scan

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
