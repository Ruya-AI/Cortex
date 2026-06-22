from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime

from sqlalchemy import select

from cortex_web.database import async_session
from cortex_web.models.github_config import RepositoryConfig
from cortex_web.models.pull_request import PullRequest
from cortex_web.services.admin_settings import AdminSettings
from cortex_web.services.github_service import GitHubService

logger = logging.getLogger(__name__)


async def fetch_prs_for_all_repos():
    """Fetch open PRs for all repos with auto_fetch_prs enabled."""
    async with async_session() as db:
        # Get admin GitHub token (single token for all repos)
        token = await AdminSettings.get_github_token(db)
        if not token:
            logger.warning("No GitHub token configured in admin settings — skipping PR fetch")
            return

        api_url = await AdminSettings.get_github_api_url(db)

        repos_result = await db.execute(
            select(RepositoryConfig).where(
                RepositoryConfig.auto_fetch_prs == True,  # noqa: E712
                RepositoryConfig.is_active == True,  # noqa: E712
            )
        )
        repos = repos_result.scalars().all()

        service = GitHubService(token=token, api_url=api_url)

        for repo in repos:
            try:
                prs_data = await service.fetch_open_prs(repo.owner, repo.repo_name)

                for pr_data in prs_data:
                    existing = await db.execute(
                        select(PullRequest).where(
                            PullRequest.repository_config_id == repo.id,
                            PullRequest.github_pr_number == pr_data["github_pr_number"],
                        )
                    )
                    existing_pr = existing.scalar_one_or_none()
                    if existing_pr:
                        existing_pr.title = pr_data["title"]
                        existing_pr.state = pr_data["state"]
                    else:
                        pr = PullRequest(
                            id=str(uuid.uuid4()),
                            repository_config_id=repo.id,
                            owner=repo.owner,
                            repo_name=repo.repo_name,
                            **pr_data,
                            fetched_at=datetime.utcnow(),
                        )
                        db.add(pr)

                await db.commit()
                logger.info("Fetched %d PRs for %s/%s", len(prs_data), repo.owner, repo.repo_name)

            except Exception as e:
                logger.error("Failed to fetch PRs for %s/%s: %s", repo.owner, repo.repo_name, e)


async def scheduled_pr_fetch_loop(interval_seconds: int = 300):
    """Run PR fetch every N seconds."""
    while True:
        try:
            await fetch_prs_for_all_repos()
        except Exception as e:
            logger.error("Scheduled PR fetch failed: %s", e)
        await asyncio.sleep(interval_seconds)
