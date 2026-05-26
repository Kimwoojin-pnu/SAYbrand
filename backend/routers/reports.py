"""리포트 API — 일간/주간 위협 요약"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.org_context import optional_current_org
from backend.models.orm import Organization
from backend.services.report_generator import generate_report

router = APIRouter(prefix="/api/reports", tags=["reports"])


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
