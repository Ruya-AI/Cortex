from __future__ import annotations

import logging

from sqlalchemy import select

from cortex_backend.database import async_session
from cortex_backend.models.automation_rule import AutomationRule
from cortex_backend.models.pull_request import PullRequest
from cortex_backend.tasks.qa_runner import run_qa_for_pr
from cortex_backend.tasks.linear_sync import create_linear_tasks_for_execution

logger = logging.getLogger(__name__)


class AutomationEngine:
    """Executes automation rules: PR -> QA -> Linear tasks."""

    async def process_pr_event(self, pr_id: str, event_type: str):
        """Process a PR event against automation rules."""
        async with async_session() as db:
            rules_result = await db.execute(
                select(AutomationRule).where(
                    AutomationRule.is_active == True,  # noqa: E712
                    AutomationRule.trigger_on == event_type,
                )
            )
            rules = rules_result.scalars().all()

            pr_result = await db.execute(select(PullRequest).where(PullRequest.id == pr_id))
            pr = pr_result.scalar_one_or_none()
            if not pr:
                return

            for rule in rules:
                # Check if rule applies to this repo
                if rule.repository_config_id and rule.repository_config_id != pr.repository_config_id:
                    continue

                logger.info("Applying rule '%s' to PR #%d", rule.name, pr.github_pr_number)

                tiers = [int(t) for t in rule.qa_tiers.split(",") if t.strip()]

                # Run QA
                await run_qa_for_pr(pr_id, tiers=tiers)

                # Create Linear tasks if configured
                if rule.create_linear_tasks and pr.last_qa_execution_id:
                    await create_linear_tasks_for_execution(
                        pr.last_qa_execution_id,
                        min_severity=rule.min_severity_for_linear,
                    )
