from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex_web.database import get_db
from cortex_web.models.github_config import GitHubConfig, RepositoryConfig
from cortex_web.models.pull_request import PullRequest
from cortex_web.services.github_service import GitHubService

router = APIRouter(prefix="/api/github", tags=["github"])


class GitHubConfigCreate(BaseModel):
    name: str
    token: str
    api_url: str = "https://api.github.com"


class RepoConfigCreate(BaseModel):
    github_config_id: str
    owner: str
    repo_name: str
    default_branch: str = "main"
    auto_fetch_prs: bool = False
    auto_qa_on_pr: bool = False
    qa_tiers: str = "1,2"


@router.get("/configs")
async def list_github_configs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GitHubConfig).order_by(GitHubConfig.created_at.desc()))
    configs = result.scalars().all()
    return {"items": [
        {"id": c.id, "name": c.name, "api_url": c.api_url, "is_active": c.is_active, "created_at": c.created_at.isoformat()}
        for c in configs
    ]}


@router.post("/configs")
async def create_github_config(data: GitHubConfigCreate, db: AsyncSession = Depends(get_db)):
    config = GitHubConfig(
        id=str(uuid.uuid4()),
        name=data.name,
        token_encrypted=data.token,  # In production, encrypt this
        api_url=data.api_url,
    )
    db.add(config)
    await db.commit()
    return {"id": config.id, "name": config.name, "status": "created"}


@router.delete("/configs/{config_id}")
async def delete_github_config(config_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GitHubConfig).where(GitHubConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    await db.delete(config)
    await db.commit()
    return {"status": "deleted"}


@router.get("/repos")
async def list_repositories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RepositoryConfig).order_by(RepositoryConfig.created_at.desc()))
    repos = result.scalars().all()
    return {"items": [
        {"id": r.id, "github_config_id": r.github_config_id, "owner": r.owner, "repo_name": r.repo_name,
         "default_branch": r.default_branch, "auto_fetch_prs": r.auto_fetch_prs, "auto_qa_on_pr": r.auto_qa_on_pr,
         "qa_tiers": r.qa_tiers, "is_active": r.is_active}
        for r in repos
    ]}


@router.post("/repos")
async def create_repository(data: RepoConfigCreate, db: AsyncSession = Depends(get_db)):
    repo = RepositoryConfig(
        id=str(uuid.uuid4()),
        github_config_id=data.github_config_id,
        owner=data.owner,
        repo_name=data.repo_name,
        default_branch=data.default_branch,
        auto_fetch_prs=data.auto_fetch_prs,
        auto_qa_on_pr=data.auto_qa_on_pr,
        qa_tiers=data.qa_tiers,
    )
    db.add(repo)
    await db.commit()
    return {"id": repo.id, "status": "created"}


@router.post("/repos/{repo_id}/fetch-prs")
async def fetch_prs(repo_id: str, db: AsyncSession = Depends(get_db)):
    """Manually fetch open PRs for a repository."""
    result = await db.execute(select(RepositoryConfig).where(RepositoryConfig.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    gh_result = await db.execute(select(GitHubConfig).where(GitHubConfig.id == repo.github_config_id))
    gh_config = gh_result.scalar_one_or_none()
    if not gh_config:
        raise HTTPException(status_code=404, detail="GitHub config not found")

    service = GitHubService(token=gh_config.token_encrypted, api_url=gh_config.api_url)
    prs_data = await service.fetch_open_prs(repo.owner, repo.repo_name)

    created_count = 0
    updated_count = 0
    for pr_data in prs_data:
        existing = await db.execute(
            select(PullRequest).where(
                PullRequest.repository_config_id == repo_id,
                PullRequest.github_pr_number == pr_data["github_pr_number"],
            )
        )
        existing_pr = existing.scalar_one_or_none()
        if existing_pr:
            existing_pr.title = pr_data["title"]
            existing_pr.state = pr_data["state"]
            existing_pr.additions = pr_data.get("additions", 0)
            existing_pr.deletions = pr_data.get("deletions", 0)
            existing_pr.changed_files = pr_data.get("changed_files", 0)
            updated_count += 1
        else:
            pr = PullRequest(
                id=str(uuid.uuid4()),
                repository_config_id=repo_id,
                owner=repo.owner,
                repo_name=repo.repo_name,
                **pr_data,
                fetched_at=datetime.utcnow(),
            )
            db.add(pr)
            created_count += 1

    await db.commit()
    return {"created": created_count, "updated": updated_count, "total_prs": len(prs_data)}
