from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from cortex_backend.database import Base

class PullRequest(Base):
    __tablename__ = "pull_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_config_id: Mapped[str] = mapped_column(String(36))
    github_pr_number: Mapped[int] = mapped_column(Integer)
    github_pr_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(String(255))
    author_avatar_url: Mapped[str] = mapped_column(String(500), default="")
    source_branch: Mapped[str] = mapped_column(String(255))
    target_branch: Mapped[str] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(20), default="open")  # open, closed, merged
    html_url: Mapped[str] = mapped_column(String(500))
    diff_url: Mapped[str] = mapped_column(String(500), default="")
    additions: Mapped[int] = mapped_column(Integer, default=0)
    deletions: Mapped[int] = mapped_column(Integer, default=0)
    changed_files: Mapped[int] = mapped_column(Integer, default=0)

    # QA status
    qa_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, running, completed, failed, skipped
    last_qa_execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Timestamps
    github_created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    github_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Owner/repo for display
    owner: Mapped[str] = mapped_column(String(255), default="")
    repo_name: Mapped[str] = mapped_column(String(255), default="")
