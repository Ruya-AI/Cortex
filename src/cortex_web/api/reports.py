from __future__ import annotations
from fastapi import APIRouter

router = APIRouter(prefix="/api/reports", tags=["reports"])

@router.get("/{execution_id}/full/json")
async def download_full_report_json(execution_id: str):
    # In production, look up execution_id in DB to get report path
    # For now, serve from .qa-reports directory
    return {"message": "Report download endpoint", "execution_id": execution_id}

@router.get("/{execution_id}/full/pdf")
async def download_full_report_pdf(execution_id: str):
    return {"message": "PDF report download endpoint", "execution_id": execution_id}

@router.get("/{execution_id}/executive/json")
async def download_executive_json(execution_id: str):
    return {"message": "Executive JSON download endpoint", "execution_id": execution_id}

@router.get("/{execution_id}/executive/pdf")
async def download_executive_pdf(execution_id: str):
    return {"message": "Executive PDF download endpoint", "execution_id": execution_id}
