from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex_web.config import settings
from cortex_web.database import get_db
from cortex_web.models.app_config import AppConfig
from cortex_web.models.github_config import RepositoryConfig
from cortex_web.models.automation_rule import AutomationRule
from cortex_web.services.admin_settings import AdminSettings

router = APIRouter(prefix="/api/admin", tags=["admin"])


# -- GitHub Settings --

class GitHubSettings(BaseModel):
    token: str = ""
    api_url: str = "https://api.github.com"
    org_name: str = ""

@router.get("/github")
async def get_github_settings(db: AsyncSession = Depends(get_db)):
    token = await AdminSettings.get(db, "github.token")
    api_url = await AdminSettings.get(db, "github.api_url", "https://api.github.com")
    org_name = await AdminSettings.get(db, "github.org_name")
    return {
        "token": "****" + token[-4:] if len(token) > 4 else ("" if not token else "****"),
        "api_url": api_url,
        "org_name": org_name,
        "is_configured": bool(token),
    }

@router.put("/github")
async def update_github_settings(data: GitHubSettings, db: AsyncSession = Depends(get_db)):
    if data.token:
        await AdminSettings.set(db, "github.token", data.token, category="github", description="GitHub Personal Access Token")
    if data.api_url:
        await AdminSettings.set(db, "github.api_url", data.api_url, category="github", description="GitHub API URL")
    if data.org_name is not None:
        await AdminSettings.set(db, "github.org_name", data.org_name, category="github", description="GitHub Organization or User name")
    await db.commit()
    return {"status": "updated"}

@router.get("/github/org-repos")
async def fetch_org_repos(db: AsyncSession = Depends(get_db)):
    """Fetch all repositories from the configured GitHub org/user."""
    token = await AdminSettings.get(db, "github.token")
    if not token:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="GitHub token not configured")
    org_name = await AdminSettings.get(db, "github.org_name")
    if not org_name:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="GitHub organization name not configured")
    api_url = await AdminSettings.get(db, "github.api_url", "https://api.github.com")

    from cortex_web.services.github_service import GitHubService
    service = GitHubService(token=token, api_url=api_url)
    repos = await service.fetch_org_repos(org_name)

    # Mark which repos are already configured
    from cortex_web.models.github_config import RepositoryConfig
    existing_result = await db.execute(select(RepositoryConfig))
    existing = {f"{r.owner}/{r.repo_name}" for r in existing_result.scalars().all()}

    for repo in repos:
        repo["already_added"] = repo["full_name"] in existing

    return {"org": org_name, "repos": repos, "total": len(repos)}


# -- Linear Settings --

class LinearSettings(BaseModel):
    api_key: str = ""
    team_id: str = ""
    workspace_name: str = ""
    auto_create_tasks: bool = False
    min_severity: str = "medium"
    max_tasks_per_scan: int = 20

@router.get("/linear")
async def get_linear_settings(db: AsyncSession = Depends(get_db)):
    config = await AdminSettings.get_group(db, "linear.")
    api_key = config.get("linear.api_key", "")
    return {
        "api_key": "****" + api_key[-4:] if len(api_key) > 4 else ("" if not api_key else "****"),
        "team_id": config.get("linear.team_id", ""),
        "workspace_name": config.get("linear.workspace_name", ""),
        "auto_create_tasks": config.get("linear.auto_create_tasks", "false") == "true",
        "min_severity": config.get("linear.min_severity", "medium"),
        "max_tasks_per_scan": int(config.get("linear.max_tasks_per_scan", "20")),
        "is_configured": bool(api_key),
    }

@router.put("/linear")
async def update_linear_settings(data: LinearSettings, db: AsyncSession = Depends(get_db)):
    if data.api_key:
        await AdminSettings.set(db, "linear.api_key", data.api_key, "linear", "Linear API Key")
    await AdminSettings.set(db, "linear.team_id", data.team_id, "linear", "Linear Team ID")
    await AdminSettings.set(db, "linear.workspace_name", data.workspace_name, "linear", "Workspace Name")
    await AdminSettings.set(db, "linear.auto_create_tasks", str(data.auto_create_tasks).lower(), "linear")
    await AdminSettings.set(db, "linear.min_severity", data.min_severity, "linear")
    await AdminSettings.set(db, "linear.max_tasks_per_scan", str(data.max_tasks_per_scan), "linear")
    await db.commit()
    return {"status": "updated"}


# -- Notification Settings --

class NotificationSettings(BaseModel):
    slack_webhook_url: str = ""
    email: str = ""
    on_critical: bool = True
    on_gate_fail: bool = True

@router.get("/notifications")
async def get_notification_settings(db: AsyncSession = Depends(get_db)):
    config = await AdminSettings.get_group(db, "notifications.")
    return {
        "slack_webhook_url": config.get("notifications.slack_webhook_url", ""),
        "email": config.get("notifications.email", ""),
        "on_critical": config.get("notifications.on_critical", "true") == "true",
        "on_gate_fail": config.get("notifications.on_gate_fail", "true") == "true",
    }

@router.put("/notifications")
async def update_notification_settings(data: NotificationSettings, db: AsyncSession = Depends(get_db)):
    await AdminSettings.set(db, "notifications.slack_webhook_url", data.slack_webhook_url, "notifications")
    await AdminSettings.set(db, "notifications.email", data.email, "notifications")
    await AdminSettings.set(db, "notifications.on_critical", str(data.on_critical).lower(), "notifications")
    await AdminSettings.set(db, "notifications.on_gate_fail", str(data.on_gate_fail).lower(), "notifications")
    await db.commit()
    return {"status": "updated"}


# -- General Settings --

@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppConfig).order_by(AppConfig.category, AppConfig.key))
    configs = result.scalars().all()

    repos_result = await db.execute(select(RepositoryConfig).where(RepositoryConfig.is_active == True))  # noqa: E712
    repo_count = len(repos_result.scalars().all())

    rules_result = await db.execute(select(AutomationRule).where(AutomationRule.is_active == True))  # noqa: E712
    rules_count = len(rules_result.scalars().all())

    return {
        "items": [
            {"key": c.key, "value": c.value if not c.key.endswith((".token", ".api_key")) else "****", "category": c.category, "description": c.description}
            for c in configs
        ],
        "features": {
            "github": settings.enable_github,
            "linear": settings.enable_linear,
            "automation": settings.enable_automation,
            "analytics": settings.enable_analytics,
        },
        "counts": {
            "repositories": repo_count,
            "automation_rules": rules_count,
        },
    }


class SettingUpdate(BaseModel):
    value: str

@router.put("/settings/{key}")
async def update_setting(key: str, data: SettingUpdate, db: AsyncSession = Depends(get_db)):
    await AdminSettings.set(db, key, data.value)
    await db.commit()
    return {"key": key, "value": data.value, "status": "updated"}


@router.get("/system-info")
async def system_info():
    info = {
        "web_version": "1.0.0",
        "features_enabled": {
            "github": settings.enable_github,
            "linear": settings.enable_linear,
            "automation": settings.enable_automation,
            "analytics": settings.enable_analytics,
        },
    }
    try:
        from qa_platform import __version__ as qa_version
        info["qa_platform_version"] = qa_version
    except ImportError:
        info["qa_platform_version"] = "unknown"
    return info
