"""리포트 API — 일간/주간/월간 위협 요약 + PDF 다운로드"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.org_context import optional_current_org
from backend.models.orm import Organization
from backend.services.report_generator import generate_pdf_report, generate_report

router = APIRouter(prefix="/api/reports", tags=["reports"])

_VALID_PERIODS = {"daily", "weekly", "monthly"}


@router.get("/{period}")
async def get_report(
    period: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
):
    if period not in _VALID_PERIODS:
        raise HTTPException(status_code=400, detail=f"period must be one of {_VALID_PERIODS}")
    return await generate_report(user["id"], period, db, org_id=org.id if org else None)


@router.get("/{period}/pdf")
async def get_report_pdf(
    period: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
):
    if period not in _VALID_PERIODS:
        raise HTTPException(status_code=400, detail=f"period must be one of {_VALID_PERIODS}")
    pdf_bytes = await generate_pdf_report(user["id"], period, db, org_id=org.id if org else None)
    filename = f"saybrand_{period}_report_{datetime.now().strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# 하위 호환성 — 기존 /daily, /weekly 경로 유지
@router.get("/daily")
async def daily_report(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
):
    return await generate_report(user["id"], "daily", db, org_id=org.id if org else None)


@router.get("/weekly")
async def weekly_report(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
):
    return await generate_report(user["id"], "weekly", db, org_id=org.id if org else None)


@router.get("/daily/pdf")
async def daily_report_pdf(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
):
    pdf_bytes = await generate_pdf_report(user["id"], "daily", db, org_id=org.id if org else None)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=saybrand-daily-report.pdf"},
    )


@router.get("/weekly/pdf")
async def weekly_report_pdf(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
):
    pdf_bytes = await generate_pdf_report(user["id"], "weekly", db, org_id=org.id if org else None)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=saybrand-weekly-report.pdf"},
    )
