from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from cortex_web.database import Base


class RepositoryConfig(Base):
    __tablename__ = "repository_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner: Mapped[str] = mapped_column(String(255))
    repo_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    auto_fetch_prs: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_qa_on_pr: Mapped[bool] = mapped_column(Boolean, default=False)
    qa_tiers: Mapped[str] = mapped_column(String(20), default="1,2")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
