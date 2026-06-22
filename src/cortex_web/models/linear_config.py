from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from cortex_web.database import Base

class LinearConfig(Base):
    __tablename__ = "linear_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    api_key_encrypted: Mapped[str] = mapped_column(Text)
    team_id: Mapped[str] = mapped_column(String(255))
    workspace_name: Mapped[str] = mapped_column(String(255), default="")
    auto_create_tasks: Mapped[bool] = mapped_column(Boolean, default=False)
    min_severity: Mapped[str] = mapped_column(String(20), default="medium")
    max_tasks_per_scan: Mapped[int] = mapped_column(default=20)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
