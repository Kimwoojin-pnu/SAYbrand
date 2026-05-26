"""네이버 검색 API 수집기 — 블로그 / 카페 / 뉴스"""
from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone

import httpx

from backend.config import settings
from backend.services.collectors.base import BaseCollector, make_post
from backend.services.collectors.compliance import remove_pii

logger = logging.getLogger(__name__)

_BASE_URL = "https://openapi.naver.com/v1/search"
_SOURCES = [
    ("blog", "bloggername", "bloggerlink"),
    ("cafearticle", "cafename", "cafeurl"),
    ("news", "originallink", None),
]


def _strip_html(text: str) -> str:
    text = html.unescape(text)
    return re.sub(r"<[^>]+>", "", text).strip()


def _parse_naver_date(postdate: str) -> datetime:
    """YYYYMMDD → datetime."""
    try:
        return datetime.strptime(postdate, "%Y%m%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


def _parse_rfc822(pubdate: str) -> datetime:
    """RFC 822 pubDate → datetime."""
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(pubdate)
    except Exception:
        return datetime.now(timezone.utc)


def _mock_posts(keyword: str) -> list[dict]:
    now = datetime.now(timezone.utc)
    return [
        make_post(
            platform="naver",
            source_account="mock_blog_user",
            content=f"[Mock] '{keyword}' 네이버 블로그 검색 결과입니다. NAVER_CLIENT_ID / NAVER_CLIENT_SECRET을 .env에 설정하면 실제 데이터가 수집됩니다.",
            post_url="https://blog.naver.com/mock/1",
            published_at=now,
            is_mock=True,
        ),
        make_post(
            platform="naver",
            source_account="mock_cafe_user",
            content=f"[Mock] '{keyword}' 네이버 카페 검색 결과입니다.",
            post_url="https://cafe.naver.com/mock/1",
            published_at=now,
            is_mock=True,
        ),
        make_post(
            platform="naver",
            source_account="뉴스 Mock",
            content=f"[Mock] '{keyword}' 네이버 뉴스 검색 결과입니다.",
            post_url="https://news.naver.com/mock/1",
            published_at=now,
            is_mock=True,
        ),
    ]


class NaverCollector(BaseCollector):
    async def search(self, keyword: str, limit: int = 25) -> list[dict]:
        if not settings.naver_client_id or not settings.naver_client_secret:
            logger.info("Naver API 키 없음 — Mock 반환")
            return _mock_posts(keyword)

        headers = {
            "X-Naver-Client-Id": settings.naver_client_id,
            "X-Naver-Client-Secret": settings.naver_client_secret,
        }

        # 블로그 10 / 카페 10 / 뉴스 5 로 분배 (합계 limit)
        allocations = {"blog": limit // 2, "cafearticle": limit // 3, "news": limit - limit // 2 - limit // 3}
        posts: list[dict] = []

        async with httpx.AsyncClient(timeout=10) as client:
            for source, acct_field, link_field in _SOURCES:
                display = allocations.get(source, 5)
                try:
                    resp = await client.get(
                        f"{_BASE_URL}/{source}.json",
                        headers=headers,
                        params={"query": keyword, "display": display, "sort": "date"},
                    )
                    if resp.status_code != 200:
                        logger.warning("Naver %s API 오류: %s", source, resp.status_code)
                        continue

                    items = resp.json().get("items", [])
                    for item in items:
                        # 계정 정보
                        account = _strip_html(item.get(acct_field, "unknown")) if acct_field else "뉴스"
                        account_url = item.get(link_field, "") if link_field else ""

                        # 날짜
                        if source == "news":
                            published_at = _parse_rfc822(item.get("pubDate", ""))
                        else:
                            published_at = _parse_naver_date(item.get("postdate", ""))

                        content = remove_pii(_strip_html(item.get("title", "") + " " + item.get("description", "")))

                        posts.append(make_post(
                            platform="naver",
                            source_account=account,
                            content=content,
                            post_url=item.get("link") or item.get("originallink", ""),
                            published_at=published_at,
                        ))
                except Exception as e:
                    logger.warning("Naver %s 수집 실패: %s", source, e)

        return posts[:limit]
