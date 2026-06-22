from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from cortex_web.database import Base

class LinearTask(Base):
    __tablename__ = "linear_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_id: Mapped[str] = mapped_column(String(36))
    finding_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    linear_issue_id: Mapped[str] = mapped_column(String(100))
    linear_issue_url: Mapped[str] = mapped_column(String(500), default="")
    linear_issue_identifier: Mapped[str] = mapped_column(String(20), default="")  # e.g., "ENG-123"

    title: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="created")  # created, in_progress, done, cancelled
    assignee: Mapped[str] = mapped_column(String(255), default="")
    priority: Mapped[str] = mapped_column(String(20), default="medium")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
