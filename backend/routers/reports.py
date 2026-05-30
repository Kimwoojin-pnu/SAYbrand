"""리포트 API — 일간/주간/월간 위협 요약 + PDF 다운로드 + 아카이브"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import delete as sql_delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.org_context import optional_current_org
from backend.models.orm import ActivityLog, ArchivedThreat, Organization
from backend.services.report_generator import generate_pdf_report, generate_report

router = APIRouter(prefix="/api/reports", tags=["reports"])

_VALID_PERIODS = {"daily", "weekly", "monthly"}


@router.get("/archives")
async def get_archives(
    date_from: str = Query(None),
    date_to: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
):
    now = datetime.utcnow()
    await db.execute(sql_delete(ArchivedThreat).where(ArchivedThreat.expires_at <= now))
    await db.commit()

    if org:
        base = select(ArchivedThreat).where(ArchivedThreat.org_id == org.id)
        count_q = select(func.count(ArchivedThreat.id)).where(ArchivedThreat.org_id == org.id)
    else:
        base = select(ArchivedThreat).where(ArchivedThreat.resolved_by_user_id == user["id"])
        count_q = select(func.count(ArchivedThreat.id)).where(ArchivedThreat.resolved_by_user_id == user["id"])

    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            base = base.where(ArchivedThreat.archived_at >= dt_from)
            count_q = count_q.where(ArchivedThreat.archived_at >= dt_from)
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            base = base.where(ArchivedThreat.archived_at <= dt_to)
            count_q = count_q.where(ArchivedThreat.archived_at <= dt_to)
        except ValueError:
            pass

    total = (await db.execute(count_q)).scalar() or 0
    result = await db.execute(
        base.order_by(ArchivedThreat.archived_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": a.id,
                "original_threat_id": a.original_threat_id,
                "resolved_by_name": a.resolved_by_name,
                "severity": a.severity,
                "threat_type": a.threat_type,
                "platform": a.platform,
                "source_account": a.source_account,
                "source_url": a.source_url,
                "content_preview": a.content_preview,
                "risk_score": a.risk_score,
                "action_taken": a.action_taken,
                "resolution_note": a.resolution_note,
                "original_detected_at": a.original_detected_at.isoformat() if a.original_detected_at else None,
                "archived_at": a.archived_at.isoformat() if a.archived_at else None,
                "expires_at": a.expires_at.isoformat() if a.expires_at else None,
            }
            for a in items
        ],
    }


@router.delete("/archives/{archive_id}")
async def delete_archive(
    archive_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
):
    result = await db.execute(select(ArchivedThreat).where(ArchivedThreat.id == archive_id))
    archive = result.scalar_one_or_none()
    if not archive:
        raise HTTPException(status_code=404, detail="아카이브를 찾을 수 없습니다.")

    now = datetime.utcnow()
    org_id = org.id if org else None
    user_name = user.get("name") or user.get("email", "")
    db.add(ActivityLog(
        org_id=org_id, user_id=user["id"], user_name=user_name,
        action_type="delete_archive",
        action_detail=f"아카이브 #{archive_id} 삭제: {archive.platform}/{archive.source_account}",
        target_id=archive_id, target_type="archive",
        created_at=now, expires_at=now + timedelta(days=7),
    ))
    await db.delete(archive)
    await db.commit()
    return {"id": archive_id, "deleted": True}


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
