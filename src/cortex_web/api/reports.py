from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex_web.database import get_db
from cortex_web.models.qa_execution import QAExecution
from cortex_web.models.qa_finding import QAFinding

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/{execution_id}")
async def get_report_info(execution_id: str, db: AsyncSession = Depends(get_db)):
    """Get report paths and summary for an execution."""
    result = await db.execute(select(QAExecution).where(QAExecution.id == execution_id))
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return {
        "execution_id": execution.id,
        "scan_id": execution.scan_id,
        "status": execution.status,
        "finding_count": execution.finding_count,
        "severity_counts": execution.severity_counts,
        "quality_gate_status": execution.quality_gate_status,
        "reports": {
            "full_json": execution.report_json_path or None,
            "full_pdf": execution.report_pdf_path or None,
            "executive_json": execution.executive_json_path or None,
            "executive_pdf": execution.executive_pdf_path or None,
        },
    }


@router.get("/{execution_id}/content/{report_type}")
async def get_report_content(execution_id: str, report_type: str, db: AsyncSession = Depends(get_db)):
    """Return JSON report content for in-browser viewing."""
    result = await db.execute(select(QAExecution).where(QAExecution.id == execution_id))
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    path_map = {
        "full": execution.report_json_path,
        "executive": execution.executive_json_path,
    }
    file_path = path_map.get(report_type)
    if not file_path:
        raise HTTPException(status_code=400, detail=f"Unknown report type: {report_type}. Use 'full' or 'executive'.")

    path = Path(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report file not found on disk")

    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        raise HTTPException(status_code=500, detail=f"Failed to read report: {e}")

    return JSONResponse(content=data)


@router.get("/{execution_id}/download/{report_type}")
async def download_report(execution_id: str, report_type: str, db: AsyncSession = Depends(get_db)):
    """Download a report file. report_type: full-json, full-pdf, executive-json, executive-pdf"""
    result = await db.execute(select(QAExecution).where(QAExecution.id == execution_id))
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    path_map = {
        "full-json": execution.report_json_path,
        "full-pdf": execution.report_pdf_path,
        "executive-json": execution.executive_json_path,
        "executive-pdf": execution.executive_pdf_path,
    }
    file_path = path_map.get(report_type)
    if not file_path:
        raise HTTPException(status_code=400, detail=f"Unknown report type: {report_type}")

    path = Path(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")

    media_type = "application/pdf" if path.suffix == ".pdf" else "application/json"
    return FileResponse(str(path), media_type=media_type, filename=path.name)


@router.get("/{execution_id}/findings")
async def get_execution_findings(
    execution_id: str,
    severity: str | None = None,
    category: str | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Get findings for an execution with optional filters."""
    query = select(QAFinding).where(QAFinding.execution_id == execution_id)
    if severity:
        query = query.where(QAFinding.severity == severity)
    if category:
        query = query.where(QAFinding.category == category)
    query = query.limit(limit)
    result = await db.execute(query)
    findings = result.scalars().all()
    return {"items": [
        {"id": f.id, "finding_id": f.finding_id, "source": f.source, "tier": f.tier,
         "category": f.category, "severity": f.severity, "confidence": f.confidence,
         "file_path": f.file_path, "start_line": f.start_line, "end_line": f.end_line,
         "title": f.title, "explanation": f.explanation[:500], "recommendation": f.recommendation[:500],
         "cwe": f.cwe, "validation_status": f.validation_status,
         "linear_task_id": f.linear_task_id}
        for f in findings
    ], "total": len(findings)}


@router.get("/{execution_id}/findings/{finding_id}")
async def get_finding_detail(execution_id: str, finding_id: str, db: AsyncSession = Depends(get_db)):
    """Get full finding detail (untruncated explanation and recommendation)."""
    result = await db.execute(
        select(QAFinding).where(QAFinding.execution_id == execution_id, QAFinding.id == finding_id)
    )
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="Finding not found")
    return {
        "id": f.id, "finding_id": f.finding_id, "source": f.source, "tier": f.tier,
        "category": f.category, "severity": f.severity, "confidence": f.confidence,
        "file_path": f.file_path, "start_line": f.start_line, "end_line": f.end_line,
        "title": f.title, "explanation": f.explanation, "recommendation": f.recommendation,
        "cwe": f.cwe, "validation_status": f.validation_status, "linear_task_id": f.linear_task_id,
    }
