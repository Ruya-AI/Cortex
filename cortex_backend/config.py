from __future__ import annotations
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Cortex QA Platform"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://cortex:cortex@localhost:5432/cortex"

    # Security
    secret_key: str = "change-me-in-production"

    # GitHub
    github_api_url: str = "https://api.github.com"

    # Linear
    linear_api_url: str = "https://api.linear.app/graphql"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Feature toggles
    enable_github: bool = True
    enable_linear: bool = True
    enable_automation: bool = True
    enable_analytics: bool = True

    # Notifications
    slack_webhook_url: str = ""
    notification_email: str = ""
    notify_on_critical: bool = True
    notify_on_gate_fail: bool = True

    class Config:
        env_prefix = "CORTEX_"
        env_file = ".env"

settings = Settings()
