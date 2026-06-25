from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from cortex_backend.models.qa_execution import QAExecution
from cortex_backend.models.qa_finding import QAFinding
from cortex_backend.models.pull_request import PullRequest
from cortex_backend.models.linear_task import LinearTask


class AnalyticsService:
    """Compute QA metrics and trends from execution history."""

    async def get_executive_dashboard(self, db: AsyncSession) -> dict:
        """Compute executive dashboard metrics."""
        # Total scans
        total_result = await db.execute(select(func.count(QAExecution.id)))
        total_scans = total_result.scalar() or 0

        # Completed scans
        completed_result = await db.execute(
            select(func.count(QAExecution.id)).where(QAExecution.status == "completed")
        )
        completed = completed_result.scalar() or 0

        # Total findings
        findings_result = await db.execute(select(func.sum(QAExecution.finding_count)))
        total_findings = findings_result.scalar() or 0

        # Pass rate
        pass_result = await db.execute(
            select(func.count(QAExecution.id)).where(QAExecution.quality_gate_status == "pass")
        )
        passes = pass_result.scalar() or 0
        pass_rate = round((passes / max(completed, 1)) * 100, 1)

        # Total cost
        cost_result = await db.execute(select(func.sum(QAExecution.cost_usd)))
        total_cost = round(cost_result.scalar() or 0, 4)

        # Average duration
        dur_result = await db.execute(
            select(func.avg(QAExecution.duration_seconds)).where(QAExecution.status == "completed")
        )
        avg_duration = round(dur_result.scalar() or 0, 1)

        # PRs tracked
        pr_result = await db.execute(select(func.count(PullRequest.id)))
        total_prs = pr_result.scalar() or 0

        # Linear tasks
        task_result = await db.execute(select(func.count(LinearTask.id)))
        total_tasks = task_result.scalar() or 0

        # Severity distribution across all findings
        severity_dist = {}
        for sev in ["critical", "high", "medium", "low", "info"]:
            sev_result = await db.execute(
                select(func.count(QAFinding.id)).where(QAFinding.severity == sev)
            )
            count = sev_result.scalar() or 0
            if count > 0:
                severity_dist[sev] = count

        # Recent executions
        recent_result = await db.execute(
            select(QAExecution).order_by(QAExecution.created_at.desc()).limit(10)
        )
        recent = recent_result.scalars().all()

        return {
            "total_scans": total_scans,
            "completed_scans": completed,
            "total_findings": total_findings,
            "avg_findings_per_scan": round(total_findings / max(completed, 1), 1),
            "quality_gate_pass_rate": pass_rate,
            "total_cost": total_cost,
            "avg_duration_seconds": avg_duration,
            "total_prs_tracked": total_prs,
            "total_linear_tasks": total_tasks,
            "severity_distribution": severity_dist,
            "recent_executions": [
                {
                    "id": e.id,
                    "repository_url": e.repository_url,
                    "status": e.status,
                    "finding_count": e.finding_count,
                    "quality_gate_status": e.quality_gate_status,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in recent
            ],
        }

    async def get_finding_patterns(self, db: AsyncSession) -> dict:
        """Analyze finding patterns across executions."""
        # Top categories
        cat_result = await db.execute(
            select(QAFinding.category, func.count(QAFinding.id).label("count"))
            .group_by(QAFinding.category)
            .order_by(func.count(QAFinding.id).desc())
            .limit(10)
        )
        top_categories = [{"category": row[0], "count": row[1]} for row in cat_result.all()]

        # Top files with most findings
        file_result = await db.execute(
            select(QAFinding.file_path, func.count(QAFinding.id).label("count"))
            .group_by(QAFinding.file_path)
            .order_by(func.count(QAFinding.id).desc())
            .limit(10)
        )
        top_files = [{"file": row[0], "count": row[1]} for row in file_result.all()]

        # Top sources (tools/agents)
        source_result = await db.execute(
            select(QAFinding.source, func.count(QAFinding.id).label("count"))
            .group_by(QAFinding.source)
            .order_by(func.count(QAFinding.id).desc())
            .limit(10)
        )
        top_sources = [{"source": row[0], "count": row[1]} for row in source_result.all()]

        return {
            "top_categories": top_categories,
            "top_files": top_files,
            "top_sources": top_sources,
        }
