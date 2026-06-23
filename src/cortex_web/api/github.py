from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex_web.database import get_db
from cortex_web.models.github_config import RepositoryConfig
from cortex_web.models.pull_request import PullRequest
from cortex_web.services.admin_settings import AdminSettings
from cortex_web.services.github_service import GitHubService

router = APIRouter(prefix="/api/github", tags=["github"])


class RepoConfigCreate(BaseModel):
    owner: str
    repo_name: str
    description: str = ""
    default_branch: str = "main"
    auto_fetch_prs: bool = False
    auto_qa_on_pr: bool = False
    qa_tiers: str = "1,2"


class RepoConfigUpdate(BaseModel):
    description: str | None = None
    default_branch: str | None = None
    auto_fetch_prs: bool | None = None
    auto_qa_on_pr: bool | None = None
    qa_tiers: str | None = None
    is_active: bool | None = None


@router.get("/repos")
async def list_repositories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RepositoryConfig).order_by(RepositoryConfig.created_at.desc()))
    repos = result.scalars().all()
    return {"items": [_repo_to_dict(r) for r in repos]}


@router.post("/repos")
async def create_repository(data: RepoConfigCreate, db: AsyncSession = Depends(get_db)):
    # Check if repo already exists
    existing = await db.execute(
        select(RepositoryConfig).where(
            RepositoryConfig.owner == data.owner,
            RepositoryConfig.repo_name == data.repo_name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Repository {data.owner}/{data.repo_name} already exists")

    repo = RepositoryConfig(
        id=str(uuid.uuid4()),
        owner=data.owner,
        repo_name=data.repo_name,
        description=data.description,
        default_branch=data.default_branch,
        auto_fetch_prs=data.auto_fetch_prs,
        auto_qa_on_pr=data.auto_qa_on_pr,
        qa_tiers=data.qa_tiers,
    )
    db.add(repo)
    await db.commit()
    return {"id": repo.id, "status": "created", "repo": f"{data.owner}/{data.repo_name}"}


@router.put("/repos/{repo_id}")
async def update_repository(repo_id: str, data: RepoConfigUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RepositoryConfig).where(RepositoryConfig.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(repo, field, value)
    await db.commit()
    return _repo_to_dict(repo)


@router.delete("/repos/{repo_id}")
async def delete_repository(repo_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RepositoryConfig).where(RepositoryConfig.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    await db.delete(repo)
    await db.commit()
    return {"status": "deleted"}


@router.post("/repos/{repo_id}/fetch-prs")
async def fetch_prs(repo_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch open PRs for a repository using the admin GitHub token."""
    result = await db.execute(select(RepositoryConfig).where(RepositoryConfig.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    token = await AdminSettings.get_github_token(db)
    if not token:
        raise HTTPException(status_code=400, detail="GitHub token not configured. Set it in Admin Settings.")

    api_url = await AdminSettings.get_github_api_url(db)
    service = GitHubService(token=token, api_url=api_url)
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


@router.get("/repos/{repo_id}/commits")
async def fetch_commits(repo_id: str, per_page: int = 30, branch: str | None = None, db: AsyncSession = Depends(get_db)):
    """Fetch recent commits for a repository."""
    result = await db.execute(select(RepositoryConfig).where(RepositoryConfig.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    token = await AdminSettings.get_github_token(db)
    if not token:
        raise HTTPException(status_code=400, detail="GitHub token not configured")

    api_url = await AdminSettings.get_github_api_url(db)
    service = GitHubService(token=token, api_url=api_url)
    commits = await service.fetch_commits(repo.owner, repo.repo_name, branch=branch or repo.default_branch, per_page=per_page)
    return {"commits": commits, "total": len(commits)}


def _repo_to_dict(r: RepositoryConfig) -> dict:
    return {
        "id": r.id,
        "owner": r.owner,
        "repo_name": r.repo_name,
        "full_name": f"{r.owner}/{r.repo_name}",
        "description": r.description,
        "default_branch": r.default_branch,
        "auto_fetch_prs": r.auto_fetch_prs,
        "auto_qa_on_pr": r.auto_qa_on_pr,
        "qa_tiers": r.qa_tiers,
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
