"""
개인정보보호법: 수집 후 90일 초과 데이터 자동 삭제
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.orm import Threat

logger = logging.getLogger(__name__)


async def purge_expired_data(db: AsyncSession) -> int:
    """90일 초과 위협 데이터 삭제. 삭제 건수 반환."""
    cutoff = datetime.utcnow() - timedelta(days=90)
    result = await db.execute(
        delete(Threat).where(Threat.detected_at < cutoff)
    )
    await db.commit()
    deleted = result.rowcount
    logger.info("90일 초과 데이터 삭제 완료: 기준 %s, 삭제 %d건", cutoff.date(), deleted)
    return deleted
