from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from cortex_web.database import Base

class GitHubConfig(Base):
    __tablename__ = "github_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    token_encrypted: Mapped[str] = mapped_column(Text)  # Encrypted PAT
    api_url: Mapped[str] = mapped_column(String(255), default="https://api.github.com")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RepositoryConfig(Base):
    __tablename__ = "repository_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    github_config_id: Mapped[str] = mapped_column(String(36))
    owner: Mapped[str] = mapped_column(String(255))
    repo_name: Mapped[str] = mapped_column(String(255))
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    auto_fetch_prs: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_qa_on_pr: Mapped[bool] = mapped_column(Boolean, default=False)
    qa_tiers: Mapped[str] = mapped_column(String(20), default="1,2")  # Comma-separated tier numbers
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
