"""
프로파일의 search_keywords를 기반으로
모든 수집기를 병렬 실행 후 결과 통합
"""
from __future__ import annotations

import asyncio
import logging

from backend.services.collectors.naver import NaverCollector
from backend.services.collectors.x_twitter import XTwitterCollector
from backend.services.collectors.youtube import YouTubeCollector
from backend.services.collectors.community_kr import KoreanCommunityCollector
from backend.services.profile_loader import LoadedProfile

logger = logging.getLogger(__name__)

naver_collector     = NaverCollector()
x_collector         = XTwitterCollector()
youtube_collector   = YouTubeCollector()
community_collector = KoreanCommunityCollector()


_NEGATIVE_COMBOS = ["불만", "불매", "최악", "실망", "별로", "환불거부", "항의"]


def _build_negative_keywords(profile: LoadedProfile) -> list[str]:
    """브랜드명 + 부정어 조합 검색 키워드 생성"""
    brand_names = profile.search_keywords[:2]
    combos = [
        f"{b} {n}"
        for b in brand_names
        for n in _NEGATIVE_COMBOS[:4]
        if f"{b} {n}" not in profile.search_keywords
    ]
    return combos


async def collect_for_profile(
    profile: LoadedProfile,
    limit_per_keyword: int = 10,
) -> list[dict]:
    """
    프로파일의 모든 검색 키워드로 전 플랫폼 수집.
    최대 10개 동시 실행 세마포어로 과부하 방지.
    """
    all_keywords = list(profile.search_keywords) + _build_negative_keywords(profile)

    tasks = []
    for keyword in all_keywords:
        tasks.extend([
            naver_collector.search(keyword, limit_per_keyword),
            x_collector.search(keyword, limit_per_keyword),
            youtube_collector.search(keyword, limit_per_keyword),
            community_collector.search(keyword, limit_per_keyword),
        ])

    semaphore = asyncio.Semaphore(10)

    async def bounded(coro):
        async with semaphore:
            return await coro

    results = await asyncio.gather(
        *[bounded(t) for t in tasks],
        return_exceptions=True,
    )

    all_posts: list[dict] = []
    for result in results:
        if isinstance(result, list):
            all_posts.extend(result)
        elif isinstance(result, Exception):
            logger.warning("수집기 실패: %s", result)

    # 중복 제거 (동일 post_url)
    seen: set[str] = set()
    unique: list[dict] = []
    for post in all_posts:
        url = post.get("post_url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(post)
        elif not url:
            unique.append(post)

    return unique
