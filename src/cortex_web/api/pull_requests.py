from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from cortex_web.database import get_db
from cortex_web.models.pull_request import PullRequest

router = APIRouter(prefix="/api/pull-requests", tags=["pull-requests"])

@router.get("/")
async def list_pull_requests(
    repo: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    query = select(PullRequest).order_by(PullRequest.fetched_at.desc())
    if repo:
        query = query.where(PullRequest.repo_name == repo)
    if status:
        query = query.where(PullRequest.qa_status == status)
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    prs = result.scalars().all()
    return {"items": [_pr_to_dict(pr) for pr in prs], "total": len(prs)}

@router.get("/{pr_id}")
async def get_pull_request(pr_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PullRequest).where(PullRequest.id == pr_id))
    pr = result.scalar_one_or_none()
    if not pr:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="PR not found")
    return _pr_to_dict(pr)

def _pr_to_dict(pr: PullRequest) -> dict:
    return {
        "id": pr.id,
        "github_pr_number": pr.github_pr_number,
        "title": pr.title,
        "author": pr.author,
        "author_avatar_url": pr.author_avatar_url,
        "source_branch": pr.source_branch,
        "target_branch": pr.target_branch,
        "state": pr.state,
        "html_url": pr.html_url,
        "additions": pr.additions,
        "deletions": pr.deletions,
        "changed_files": pr.changed_files,
        "qa_status": pr.qa_status,
        "owner": pr.owner,
        "repo_name": pr.repo_name,
        "fetched_at": pr.fetched_at.isoformat() if pr.fetched_at else None,
    }
