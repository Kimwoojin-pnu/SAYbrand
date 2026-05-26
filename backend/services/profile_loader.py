"""
프로파일 중앙 로더 — 인메모리 캐싱(TTL 5분) + 업종별 설정
모든 분석 단계에서 공통으로 사용한다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.orm import (
    CustomerAlias,
    CustomerExecutive,
    CustomerProfile,
    CustomerSocialAccount,
)

logger = logging.getLogger(__name__)

# ── 업종별 리스크 설정 ─────────────────────────────────────────────────────────
INDUSTRY_CONFIG: dict[str, dict] = {
    "beauty":   {"risk_multiplier": 1.1, "alert_threshold": 55,
                 "sensitive_keywords": ["성분", "피부", "부작용", "알레르기", "발진", "독성"]},
    "finance":  {"risk_multiplier": 1.3, "alert_threshold": 45,
                 "sensitive_keywords": ["사기", "횡령", "금감원", "검찰", "압수수색", "분식"]},
    "food":     {"risk_multiplier": 1.2, "alert_threshold": 50,
                 "sensitive_keywords": ["식중독", "이물질", "리콜", "발암", "불량", "유해"]},
    "fashion":  {"risk_multiplier": 1.0, "alert_threshold": 60,
                 "sensitive_keywords": ["짝퉁", "가품", "도용", "표절"]},
    "tech":     {"risk_multiplier": 1.1, "alert_threshold": 55,
                 "sensitive_keywords": ["해킹", "유출", "보안", "취약점", "랜섬웨어"]},
    "general":  {"risk_multiplier": 1.0, "alert_threshold": 60,
                 "sensitive_keywords": []},
}


@dataclass
class LoadedProfile:
    profile_id: int
    display_name: str
    industry: str
    logo_url: str | None
    profile_type: str                     # "company" | "individual"
    aliases: list[tuple[str, float]]      # [("삼성전자", 1.0), ...]
    official_handles: dict[str, str]      # {"instagram": "@samsung_kr"}
    executives: list[dict]                # [{"name": ..., "role": ..., "priority": ..., "photo_url": ...}]
    search_keywords: list[str]            # 수집기에 전달할 키워드 목록
    industry_config: dict
    loaded_at: datetime = field(default_factory=datetime.utcnow)


_TTL_SECONDS = 300  # 5분


class ProfileLoader:
    """인메모리 캐시 기반 프로파일 로더 (싱글턴)."""

    def __init__(self) -> None:
        self._cache: dict[int, LoadedProfile] = {}

    def invalidate(self, profile_id: int) -> None:
        self._cache.pop(profile_id, None)

    async def load(self, profile_id: int, db: AsyncSession) -> LoadedProfile | None:
        cached = self._cache.get(profile_id)
        if cached and (datetime.utcnow() - cached.loaded_at).total_seconds() < _TTL_SECONDS:
            return cached

        profile = await db.get(CustomerProfile, profile_id)
        if not profile:
            logger.warning("ProfileLoader: profile_id=%s 없음", profile_id)
            return None

        aliases_result = await db.execute(
            select(CustomerAlias)
            .where(CustomerAlias.profile_id == profile_id)
            .order_by(CustomerAlias.weight.desc())
        )
        aliases = aliases_result.scalars().all()

        accounts_result = await db.execute(
            select(CustomerSocialAccount).where(CustomerSocialAccount.profile_id == profile_id)
        )
        accounts = accounts_result.scalars().all()

        executives_result = await db.execute(
            select(CustomerExecutive)
            .where(CustomerExecutive.profile_id == profile_id)
            .order_by(CustomerExecutive.priority.asc())
        )
        executives = executives_result.scalars().all()

        industry = (profile.industry or "general").lower()
        industry_cfg = INDUSTRY_CONFIG.get(industry, INDUSTRY_CONFIG["general"])

        loaded = LoadedProfile(
            profile_id=profile_id,
            display_name=profile.display_name,
            industry=industry,
            logo_url=profile.logo_url,
            profile_type=profile.profile_type,
            aliases=[(a.alias, a.weight) for a in aliases],
            official_handles={s.platform: s.handle for s in accounts},
            executives=[
                {"name": e.name, "role": e.role, "priority": e.priority, "photo_url": e.photo_url}
                for e in executives
            ],
            search_keywords=_build_search_keywords(profile, aliases, executives),
            industry_config=industry_cfg,
        )
        self._cache[profile_id] = loaded
        return loaded

    async def load_for_user(self, user_id: int, db: AsyncSession) -> LoadedProfile | None:
        """사용자의 첫 번째 프로파일을 로드한다."""
        result = await db.execute(
            select(CustomerProfile).where(CustomerProfile.user_id == user_id).limit(1)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return None
        return await self.load(profile.id, db)


def _build_search_keywords(
    profile: CustomerProfile,
    aliases: list,
    executives: list,
) -> list[str]:
    keywords = [profile.display_name]
    keywords += [a.alias for a in aliases]
    keywords += [e.name for e in executives if e.priority <= 2]
    return list(dict.fromkeys(k for k in keywords if k))


# 싱글턴 인스턴스
profile_loader = ProfileLoader()
