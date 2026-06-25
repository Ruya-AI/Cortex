from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex_backend.config import settings
from cortex_backend.database import get_db
from cortex_backend.models.app_config import AppConfig
from cortex_backend.models.github_config import RepositoryConfig
from cortex_backend.models.automation_rule import AutomationRule
from cortex_backend.services.admin_settings import AdminSettings

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
        api_url = data.api_url.rstrip("/")
        if api_url == "https://github.com":
            api_url = "https://api.github.com"
        await AdminSettings.set(db, "github.api_url", api_url, category="github", description="GitHub API URL")
    if data.org_name is not None:
        await AdminSettings.set(db, "github.org_name", data.org_name.strip(), category="github", description="GitHub Organization or User name")
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

    from cortex_backend.services.github_service import GitHubService
    service = GitHubService(token=token, api_url=api_url)
    repos = await service.fetch_org_repos(org_name)

    # Mark which repos are already configured
    from cortex_backend.models.github_config import RepositoryConfig
    existing_result = await db.execute(select(RepositoryConfig))
    existing = {f"{r.owner}/{r.repo_name}" for r in existing_result.scalars().all()}

    for repo in repos:
        repo["already_added"] = repo["full_name"] in existing

    return {"org": org_name, "repos": repos, "total": len(repos)}


# -- Linear Settings --

class LinearSettings(BaseModel):
    api_key: str | None = None
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
    slack = config.get("notifications.slack_webhook_url", "")
    email = config.get("notifications.email", "")
    return {
        "slack_webhook_url": slack,
        "email": email,
        "on_critical": config.get("notifications.on_critical", "true") == "true",
        "on_gate_fail": config.get("notifications.on_gate_fail", "true") == "true",
        "is_configured": bool(slack or email),
    }

@router.put("/notifications")
async def update_notification_settings(data: NotificationSettings, db: AsyncSession = Depends(get_db)):
    await AdminSettings.set(db, "notifications.slack_webhook_url", data.slack_webhook_url, "notifications")
    await AdminSettings.set(db, "notifications.email", data.email, "notifications")
    await AdminSettings.set(db, "notifications.on_critical", str(data.on_critical).lower(), "notifications")
    await AdminSettings.set(db, "notifications.on_gate_fail", str(data.on_gate_fail).lower(), "notifications")
    await db.commit()
    return {"status": "updated"}


# -- LLM Settings --

class LLMSettings(BaseModel):
    provider: str = "vertex_ai"
    api_key: str | None = None
    primary_model: str = "claude-opus-4-6"
    fallback_model: str = "claude-sonnet-4-6"
    vertex_project_id: str = ""
    vertex_region: str = "global"
    max_tokens: int = 8192
    temperature: float = 0.0
    max_retries: int = 3
    cost_limit: float = 0.0

@router.get("/llm")
async def get_llm_settings(db: AsyncSession = Depends(get_db)):
    config = await AdminSettings.get_group(db, "llm.")
    api_key = config.get("llm.api_key", "")
    return {
        "provider": config.get("llm.provider", "vertex_ai"),
        "api_key": "****" + api_key[-4:] if len(api_key) > 4 else ("" if not api_key else "****"),
        "primary_model": config.get("llm.primary_model", "claude-opus-4-6"),
        "fallback_model": config.get("llm.fallback_model", "claude-sonnet-4-6"),
        "vertex_project_id": config.get("llm.vertex_project_id", ""),
        "vertex_region": config.get("llm.vertex_region", "global"),
        "max_tokens": int(config.get("llm.max_tokens", "8192")),
        "temperature": float(config.get("llm.temperature", "0.0")),
        "max_retries": int(config.get("llm.max_retries", "3")),
        "cost_limit": float(config.get("llm.cost_limit", "0.0")),
        "is_configured": bool(api_key or config.get("llm.vertex_project_id", "")),
    }

@router.put("/llm")
async def update_llm_settings(data: LLMSettings, db: AsyncSession = Depends(get_db)):
    await AdminSettings.set(db, "llm.provider", data.provider, "llm", "LLM Provider (vertex_ai or anthropic)")
    if data.api_key:
        await AdminSettings.set(db, "llm.api_key", data.api_key, "llm", "Anthropic API Key")
    await AdminSettings.set(db, "llm.primary_model", data.primary_model, "llm", "Primary model ID")
    await AdminSettings.set(db, "llm.fallback_model", data.fallback_model, "llm", "Fallback model ID")
    await AdminSettings.set(db, "llm.vertex_project_id", data.vertex_project_id, "llm", "GCP Project ID for Vertex AI")
    await AdminSettings.set(db, "llm.vertex_region", data.vertex_region, "llm", "Vertex AI region")
    await AdminSettings.set(db, "llm.max_tokens", str(data.max_tokens), "llm", "Max tokens per LLM call")
    await AdminSettings.set(db, "llm.temperature", str(data.temperature), "llm", "Temperature (0.0 = deterministic)")
    await AdminSettings.set(db, "llm.max_retries", str(data.max_retries), "llm", "Max retries on transient errors")
    await AdminSettings.set(db, "llm.cost_limit", str(data.cost_limit), "llm", "Default cost limit per scan (0 = unlimited)")
    await db.commit()
    return {"status": "updated"}


# -- QA Settings --

class QASettings(BaseModel):
    stale_execution_timeout_minutes: int = 60

    def model_post_init(self, __context):
        if self.stale_execution_timeout_minutes < 5:
            self.stale_execution_timeout_minutes = 5
        elif self.stale_execution_timeout_minutes > 1440:
            self.stale_execution_timeout_minutes = 1440

@router.get("/qa")
async def get_qa_settings(db: AsyncSession = Depends(get_db)):
    timeout = await AdminSettings.get(db, "qa.stale_execution_timeout_minutes", "60")
    return {
        "stale_execution_timeout_minutes": int(timeout),
    }

@router.put("/qa")
async def update_qa_settings(data: QASettings, db: AsyncSession = Depends(get_db)):
    await AdminSettings.set(db, "qa.stale_execution_timeout_minutes", str(data.stale_execution_timeout_minutes), "qa", "Minutes before a running execution is considered stale and auto-failed")
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
        "version": "2.0.0",
        "features_enabled": {
            "github": settings.enable_github,
            "linear": settings.enable_linear,
            "automation": settings.enable_automation,
            "analytics": settings.enable_analytics,
        },
    }
    try:
        from cortex_engine import __version__ as qa_version
        info["engine_version"] = qa_version
    except ImportError:
        info["engine_version"] = "unknown"
    return info
