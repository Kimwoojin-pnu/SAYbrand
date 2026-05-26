from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.orm import CustomerAlias, CustomerSocialAccount
from backend.models.schemas import EntityResolverResult


async def resolve_entity(
    content: str,
    account_name: str,
    profile_id: int,
    db: AsyncSession,
) -> EntityResolverResult:
    # 1. 프로파일의 모든 alias 로드
    alias_result = await db.execute(
        select(CustomerAlias).where(CustomerAlias.profile_id == profile_id)
    )
    aliases = alias_result.scalars().all()

    # 2. 공식 계정 로드 — 공식 계정에서 올라온 콘텐츠는 위협 아님
    account_result = await db.execute(
        select(CustomerSocialAccount).where(CustomerSocialAccount.profile_id == profile_id)
    )
    official_accounts = account_result.scalars().all()

    matched_accounts = [
        a.handle for a in official_accounts
        if account_name.lower().strip("@") == a.handle.lower().strip("@")
    ]
    if matched_accounts:
        return EntityResolverResult(
            relevance_score=0.0,
            matched_aliases=[],
            matched_accounts=matched_accounts,
            is_relevant=False,
            confidence="high",
        )

    # 3. alias 매칭 점수 계산
    content_lower = content.lower()
    matched_aliases: list[str] = []
    weighted_score = 0.0
    total_weight = sum(a.weight for a in aliases) or 1.0

    for alias in aliases:
        if alias.alias.lower() in content_lower:
            matched_aliases.append(alias.alias)
            weighted_score += alias.weight

    relevance_score = round(min(weighted_score / total_weight, 1.0), 4)
    is_relevant = relevance_score >= 0.5

    if relevance_score >= 0.8:
        confidence = "high"
    elif relevance_score >= 0.5:
        confidence = "medium"
    else:
        confidence = "low"

    return EntityResolverResult(
        relevance_score=relevance_score,
        matched_aliases=matched_aliases,
        matched_accounts=[],
        is_relevant=is_relevant,
        confidence=confidence,
    )


async def resolve_entity_with_profile(
    content: str,
    account_name: str,
    profile,  # ProfileLoader.LoadedProfile
) -> dict:
    """
    ProfileLoader 기반 entity resolver.
    기존 DB 쿼리 없이 이미 로드된 프로파일로 판단한다.
    """
    # 1. 공식 계정 → 즉시 제외
    account_clean = account_name.lower().lstrip("@")
    for handle in profile.official_handles.values():
        if handle.lower().lstrip("@") == account_clean:
            return {
                "is_relevant": False,
                "reason": "own_official_account",
                "relevance_score": 0.0,
                "matched_aliases": [],
                "confidence": "high",
            }

    # 2. alias 가중치 매칭
    content_lower = content.lower()
    total_weight = sum(w for _, w in profile.aliases) or 1.0
    matched_weight = 0.0
    matched: list[str] = []

    for alias, weight in profile.aliases:
        if alias.lower() in content_lower:
            matched_weight += weight
            matched.append(alias)

    relevance_score = matched_weight / total_weight

    # 3. 임직원 이름 보너스
    exec_bonus = 0.0
    for exec_info in profile.executives:
        if exec_info["name"] in content:
            priority = exec_info.get("priority", 2)
            exec_bonus += 0.2 * (1.0 / priority)

    relevance_score = min(relevance_score + exec_bonus, 1.0)

    # 4. 업종별 임계값
    threshold = 0.5 / profile.industry_config["risk_multiplier"]

    if relevance_score >= 0.7:
        confidence = "high"
    elif relevance_score >= threshold:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "is_relevant": relevance_score >= threshold,
        "relevance_score": round(relevance_score, 3),
        "matched_aliases": matched,
        "threshold_used": round(threshold, 3),
        "confidence": confidence,
    }
