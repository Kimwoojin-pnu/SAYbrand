"""YouTube Data API v3 수집기 — 영상 검색 + 댓글 수집"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from backend.config import settings
from backend.services.collectors.base import BaseCollector, make_post
from backend.services.collectors.compliance import remove_pii

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_COMMENTS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


def _parse_iso(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc)


def _mock_posts(keyword: str) -> list[dict]:
    now = datetime.now(timezone.utc)
    return [
        make_post(
            platform="youtube",
            source_account="Mock_Channel_1",
            content=f"[Mock] '{keyword}' YouTube 영상 검색 결과입니다. YOUTUBE_API_KEY를 .env에 설정하면 실제 데이터가 수집됩니다.",
            post_url="https://youtube.com/watch?v=mock001",
            published_at=now,
            likes=250,
            comments=42,
            is_mock=True,
        ),
        make_post(
            platform="youtube",
            source_account="Mock_Channel_2",
            content=f"[Mock] '{keyword}' 관련 두 번째 YouTube 영상입니다.",
            post_url="https://youtube.com/watch?v=mock002",
            published_at=now,
            likes=1200,
            comments=88,
            is_mock=True,
        ),
    ]


class YouTubeCollector(BaseCollector):
    async def search(self, keyword: str, limit: int = 10, days_back: int = 7) -> list[dict]:
        if not settings.youtube_api_key:
            logger.info("YouTube API 키 없음 — Mock 반환")
            return _mock_posts(keyword)

        try:
            return await self._search_real(keyword, limit, days_back)
        except Exception as e:
            logger.warning("YouTube 수집 실패: %s — Mock 반환", e)
            return _mock_posts(keyword)

    async def _search_real(self, keyword: str, limit: int, days_back: int = 7) -> list[dict]:
        from datetime import timedelta
        published_after = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")

        async with httpx.AsyncClient(timeout=15) as client:
            # 영상 검색
            resp = await client.get(
                _SEARCH_URL,
                params={
                    "q": keyword,
                    "part": "snippet",
                    "type": "video",
                    "order": "date",
                    "maxResults": min(limit, 50),
                    "relevanceLanguage": "ko",
                    "publishedAfter": published_after,
                    "key": settings.youtube_api_key,
                },
            )
            if resp.status_code != 200:
                logger.warning("YouTube Search API 오류: %s", resp.status_code)
                return _mock_posts(keyword)

            items = resp.json().get("items", [])
            if not items:
                return []

            video_ids = [it["id"]["videoId"] for it in items if it.get("id", {}).get("videoId")]

            # 통계 조회
            stats_map: dict[str, dict] = {}
            if video_ids:
                stats_resp = await client.get(
                    _VIDEOS_URL,
                    params={
                        "id": ",".join(video_ids),
                        "part": "statistics",
                        "key": settings.youtube_api_key,
                    },
                )
                if stats_resp.status_code == 200:
                    for v in stats_resp.json().get("items", []):
                        stats_map[v["id"]] = v.get("statistics", {})

        posts: list[dict] = []
        for item in items:
            vid_id = item.get("id", {}).get("videoId", "")
            snippet = item.get("snippet", {})
            stats = stats_map.get(vid_id, {})

            channel = snippet.get("channelTitle", "unknown")
            title = snippet.get("title", "")
            desc = snippet.get("description", "")[:300]
            content = remove_pii(f"{title}\n{desc}".strip())

            published_at = _parse_iso(snippet.get("publishedAt", ""))
            post_url = f"https://www.youtube.com/watch?v={vid_id}" if vid_id else ""

            posts.append(make_post(
                platform="youtube",
                source_account=channel,
                content=content,
                post_url=post_url,
                published_at=published_at,
                likes=int(stats.get("likeCount", 0) or 0),
                comments=int(stats.get("commentCount", 0) or 0),
                shares=int(stats.get("favoriteCount", 0) or 0),
                is_mock=False,
            ))

        return posts[:limit]
