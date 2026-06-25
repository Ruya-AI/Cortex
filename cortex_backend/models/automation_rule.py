from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from cortex_backend.database import Base

class AutomationRule(Base):
    __tablename__ = "automation_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")

    # Trigger conditions
    trigger_on: Mapped[str] = mapped_column(String(50))  # pr_opened, pr_updated, schedule, manual
    repository_config_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # NULL = all repos

    # QA config
    qa_tiers: Mapped[str] = mapped_column(String(20), default="1,2")

    # Post-QA actions
    create_linear_tasks: Mapped[bool] = mapped_column(Boolean, default=False)
    post_github_comment: Mapped[bool] = mapped_column(Boolean, default=True)
    min_severity_for_linear: Mapped[str] = mapped_column(String(20), default="medium")

    # Scheduling
    schedule_cron: Mapped[str] = mapped_column(String(100), default="")  # Cron expression for scheduled triggers

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
