from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex_web.models.app_config import AppConfig


class AdminSettings:
    """Read/write admin-level settings from the app_configs table."""

    @staticmethod
    async def get(db: AsyncSession, key: str, default: str = "") -> str:
        result = await db.execute(select(AppConfig).where(AppConfig.key == key))
        config = result.scalar_one_or_none()
        return config.value if config else default

    @staticmethod
    async def set(db: AsyncSession, key: str, value: str, category: str = "general", description: str = "") -> None:
        result = await db.execute(select(AppConfig).where(AppConfig.key == key))
        config = result.scalar_one_or_none()
        if config:
            config.value = value
            if description:
                config.description = description
        else:
            config = AppConfig(key=key, value=value, category=category, description=description)
            db.add(config)

    @staticmethod
    async def get_group(db: AsyncSession, prefix: str) -> dict[str, str]:
        """Get all settings with a given prefix (e.g., 'github.')."""
        result = await db.execute(
            select(AppConfig).where(AppConfig.key.startswith(prefix))
        )
        configs = result.scalars().all()
        return {c.key: c.value for c in configs}

    @staticmethod
    async def get_github_token(db: AsyncSession) -> str:
        return await AdminSettings.get(db, "github.token")

    @staticmethod
    async def get_github_api_url(db: AsyncSession) -> str:
        return await AdminSettings.get(db, "github.api_url", "https://api.github.com")

    @staticmethod
    async def get_linear_config(db: AsyncSession) -> dict[str, str]:
        return await AdminSettings.get_group(db, "linear.")
