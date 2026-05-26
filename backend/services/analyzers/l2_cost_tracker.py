"""L2 API 사용량 추적 — 고객별 비용 기록"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.orm import UsageLog

logger = logging.getLogger(__name__)

# 모델별 1K 토큰당 USD 비용 (근사값)
COST_PER_1K_TOKENS: dict[str, float] = {
    "hyperclova": 0.002,
    "gemini": 0.001,
    "mock": 0.0,
    "claude": 0.003,
}


async def record_usage(
    db: AsyncSession,
    user_id: int,
    model: str,
    layer: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    profile_id: int | None = None,
) -> None:
    """
    API 호출 1건의 사용량을 usage_logs 테이블에 기록한다.

    Args:
        db: AsyncSession
        user_id: 요청 유저 ID
        model: "hyperclova" | "gemini" | "mock" | "claude"
        layer: "L2_text" | "L2_image" | "L3"
        tokens_in: 입력 토큰 수
        tokens_out: 출력 토큰 수
        profile_id: 분석 대상 CustomerProfile ID (선택)
    """
    total = tokens_in + tokens_out
    cost = (total / 1000) * COST_PER_1K_TOKENS.get(model, 0.0)

    log = UsageLog(
        user_id=user_id,
        profile_id=profile_id,
        model=model,
        layer=layer,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=round(cost, 6),
        created_at=datetime.utcnow(),
    )
    db.add(log)
    try:
        await db.commit()
    except Exception as e:
        logger.warning("UsageLog 기록 실패: %s", e)
        await db.rollback()


async def get_usage_summary(
    db: AsyncSession,
    user_id: int,
) -> dict:
    """유저의 누적 사용량과 비용 합계를 반환한다."""
    from sqlalchemy import select, func
    result = await db.execute(
        select(
            UsageLog.model,
            func.sum(UsageLog.tokens_in + UsageLog.tokens_out).label("total_tokens"),
            func.sum(UsageLog.cost_usd).label("total_cost"),
            func.count(UsageLog.id).label("call_count"),
        )
        .where(UsageLog.user_id == user_id)
        .group_by(UsageLog.model)
    )
    rows = result.all()
    return {
        "by_model": [
            {
                "model": r.model,
                "total_tokens": int(r.total_tokens or 0),
                "total_cost_usd": round(float(r.total_cost or 0), 6),
                "call_count": int(r.call_count),
            }
            for r in rows
        ],
        "total_cost_usd": round(sum(float(r.total_cost or 0) for r in rows), 6),
    }
