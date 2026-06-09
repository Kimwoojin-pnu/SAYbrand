"""리포트 API — 일간/주간/월간 위협 요약 + PDF 다운로드 + 아카이브 + 위협 인텔리전스 맵"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import delete as sql_delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.org_context import optional_current_org
from backend.models.orm import ActivityLog, ArchivedThreat, CustomerProfile, Organization, Threat
from backend.services.report_generator import generate_pdf_report, generate_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])

_PLATFORM_META = {
    "instagram": {"age_group": "10-30대", "tendency": "감성·이미지 중심"},
    "youtube":   {"age_group": "10-40대", "tendency": "정보·리뷰 중심"},
    "x":         {"age_group": "20-40대", "tendency": "이슈·여론 중심"},
    "tiktok":    {"age_group": "10-20대", "tendency": "트렌드·숏폼 중심"},
    "naver":     {"age_group": "20-50대", "tendency": "검색·커뮤니티 중심"},
}

_VALID_PERIODS = {"daily", "weekly", "monthly"}


@router.get("/threat-map")
async def get_threat_map(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
):
    try:
        return await _build_threat_map(db, user, org)
    except Exception as e:
        logger.error("threat-map 오류: %s", e, exc_info=True)
        print(f"[THREAT-MAP ERROR] {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


async def _build_threat_map(db, user, org):
    user_id = user["id"]
    org_id = org.id if org else None
    base_filter = Threat.org_id == org_id if org_id else Threat.user_id == user_id

    p_result = await db.execute(
        select(CustomerProfile).where(CustomerProfile.user_id == user_id).limit(1)
    )
    profile = p_result.scalar_one_or_none()
    brand_name = profile.display_name if profile else "내 브랜드"

    total = (await db.execute(select(func.count(Threat.id)).where(base_filter))).scalar() or 0
    if total == 0:
        return {"brand_name": brand_name, "total_threats": 0, "platforms": []}

    agg = await db.execute(
        select(
            Threat.platform,
            Threat.severity,
            Threat.sentiment,
            Threat.emotion,
            func.count(Threat.id).label("cnt"),
            func.avg(Threat.risk_score).label("avg_risk"),
        )
        .where(base_filter)
        .group_by(Threat.platform, Threat.severity, Threat.sentiment, Threat.emotion)
    )
    rows = agg.all()

    org_result = await db.execute(
        select(Threat)
        .where(base_filter, Threat.is_organized.is_(True))
        .order_by(Threat.detected_at.desc())
        .limit(100)
    )
    organized = org_result.scalars().all()

    pdata: dict[str, dict] = {}
    for row in rows:
        p = (row.platform or "unknown").lower()
        if p not in pdata:
            pdata[p] = {
                "total": 0,
                "severity": {"critical": 0, "high": 0, "medium": 0, "low": 0, "feedback": 0},
                "sentiment": {"negative": 0, "neutral": 0, "positive": 0},
                "emotions": {},
                "risk_sum": 0.0,
            }
        d = pdata[p]
        d["total"] += int(row.cnt)
        d["risk_sum"] += float(row.avg_risk or 0) * int(row.cnt)
        if row.severity and row.severity in d["severity"]:
            d["severity"][row.severity] += int(row.cnt)
        if row.sentiment and row.sentiment in d["sentiment"]:
            d["sentiment"][row.sentiment] += int(row.cnt)
        if row.emotion:
            d["emotions"][row.emotion] = d["emotions"].get(row.emotion, 0) + int(row.cnt)

    org_by_p: dict[str, list] = {}
    for t in organized:
        p = (t.platform or "unknown").lower()
        org_by_p.setdefault(p, []).append(t)

    platforms = []
    for p, d in pdata.items():
        meta = _PLATFORM_META.get(p, {"age_group": "전체", "tendency": "일반"})
        org_attacks = org_by_p.get(p, [])
        top_emotions = sorted(d["emotions"].items(), key=lambda x: x[1], reverse=True)[:3]
        avg_risk = int(d["risk_sum"] / d["total"]) if d["total"] else 0
        platforms.append({
            "platform": p,
            "age_group": meta["age_group"],
            "tendency": meta["tendency"],
            "total": d["total"],
            "severity_breakdown": d["severity"],
            "sentiment_breakdown": d["sentiment"],
            "top_emotions": [{"emotion": e, "count": int(c)} for e, c in top_emotions],
            "organized_count": len(org_attacks),
            "organized_attacks": [
                {
                    "id": t.id,
                    "detected_at": t.detected_at.isoformat() if t.detected_at else None,
                    "threat_type": t.threat_type or "",
                    "severity": t.severity or "unknown",
                    "source_account": t.source_account or "",
                    "content_preview": (t.content_preview or "")[:100],
                    "risk_score": int(t.risk_score or 0),
                }
                for t in org_attacks[:5]
            ],
            "avg_risk_score": avg_risk,
        })

    platforms.sort(key=lambda x: x["total"], reverse=True)
    return {"brand_name": brand_name, "total_threats": int(total), "platforms": platforms}


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
