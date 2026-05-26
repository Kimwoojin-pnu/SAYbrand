"""7일 기준선 대비 급증 이상 감지"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.orm import Threat


async def detect_anomaly(
    user_id: int,
    db: AsyncSession,
    window_hours: int = 1,
    baseline_days: int = 7,
    ratio_threshold: float = 2.0,
) -> dict:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=window_hours)
    baseline_start = now - timedelta(days=baseline_days)

    recent_result = await db.execute(
        select(func.count(Threat.id)).where(
            Threat.user_id == user_id,
            Threat.detected_at >= window_start,
        )
    )
    recent_count = recent_result.scalar() or 0

    baseline_result = await db.execute(
        select(func.count(Threat.id)).where(
            Threat.user_id == user_id,
            Threat.detected_at >= baseline_start,
            Threat.detected_at < window_start,
        )
    )
    baseline_total = baseline_result.scalar() or 0

    hours_in_baseline = baseline_days * 24 - window_hours
    baseline_avg = baseline_total / max(hours_in_baseline, 1)
    expected = baseline_avg * window_hours

    is_anomaly = expected > 0 and (recent_count / expected) >= ratio_threshold
    ratio = (recent_count / expected) if expected > 0 else 0.0

    return {
        "is_anomaly": is_anomaly,
        "recent_count": recent_count,
        "expected_count": round(expected, 2),
        "ratio": round(ratio, 2),
        "threshold": ratio_threshold,
        "window_hours": window_hours,
    }
