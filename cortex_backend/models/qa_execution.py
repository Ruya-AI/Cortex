from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from cortex_backend.database import Base

class QAExecution(Base):
    __tablename__ = "qa_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pull_request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # NULL for ad-hoc scans
    scan_id: Mapped[str] = mapped_column(String(100), default="")  # Maps to cortex_engine scan_id

    # Repository info
    repository_url: Mapped[str] = mapped_column(String(500))
    branch: Mapped[str] = mapped_column(String(255), default="")
    commit_sha: Mapped[str] = mapped_column(String(64), default="")

    # Execution config
    tiers: Mapped[str] = mapped_column(String(20), default="1,2")
    execution_type: Mapped[str] = mapped_column(String(20), default="repository")  # repository, pull_request, commit
    trigger: Mapped[str] = mapped_column(String(20), default="web-ui")  # web-ui, automated, webhook

    # Results
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, running, completed, failed, cancelled
    finding_count: Mapped[int] = mapped_column(Integer, default=0)
    severity_counts: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    quality_gate_status: Mapped[str] = mapped_column(String(20), default="")

    # Reports
    report_json_path: Mapped[str] = mapped_column(String(500), default="")
    report_pdf_path: Mapped[str] = mapped_column(String(500), default="")
    executive_json_path: Mapped[str] = mapped_column(String(500), default="")
    executive_pdf_path: Mapped[str] = mapped_column(String(500), default="")

    # Metrics
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    # Logs
    execution_log: Mapped[str] = mapped_column(Text, default="")
    error_message: Mapped[str] = mapped_column(Text, default="")

    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
