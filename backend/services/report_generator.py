"""리포트 생성 서비스 — 일간/주간 위협 요약"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.orm import Threat


async def generate_report(
    user_id: int,
    period: str,
    db: AsyncSession,
    org_id: int | None = None,
) -> dict:
    """
    period: "daily" (24시간) | "weekly" (7일)
    org_id: 조직 기준 필터링. None이면 user_id 기준.
    """
    now = datetime.now(timezone.utc)
    days = 1 if period == "daily" else 7
    since = now - timedelta(days=days)
    period_label = f"{since.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}"

    def _scope(q):
        if org_id is not None:
            return q.where(Threat.org_id == org_id, Threat.detected_at >= since)
        return q.where(Threat.user_id == user_id, Threat.detected_at >= since)

    total_result = await db.execute(_scope(select(func.count(Threat.id))))
    total = total_result.scalar() or 0

    # 심각도별
    sev_result = await db.execute(
        _scope(select(Threat.severity, func.count(Threat.id))).group_by(Threat.severity)
    )
    by_severity = {row[0]: row[1] for row in sev_result}

    # 플랫폼별
    plat_result = await db.execute(
        _scope(select(Threat.platform, func.count(Threat.id))).group_by(Threat.platform)
    )
    by_platform = {row[0]: row[1] for row in plat_result}

    # 해결 완료
    resolved_result = await db.execute(
        _scope(select(func.count(Threat.id))).where(Threat.status == "resolved")
    )
    resolved_count = resolved_result.scalar() or 0

    # TOP 5 위협
    top_result = await db.execute(
        _scope(select(Threat)).order_by(Threat.risk_score.desc()).limit(5)
    )
    top_threats = [
        {
            "id": t.id,
            "severity": t.severity,
            "platform": t.platform,
            "source_account": t.source_account,
            "content_preview": t.content_preview,
            "risk_score": t.risk_score,
            "status": t.status,
            "source_url": t.source_url,
        }
        for t in top_result.scalars().all()
    ]

    return {
        "period": period_label,
        "total_threats": total,
        "by_severity": by_severity,
        "by_platform": by_platform,
        "top_threats": top_threats,
        "resolved_count": resolved_count,
        "is_mock": total == 0,
    }
