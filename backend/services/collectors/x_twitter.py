"""X (Twitter) API v2 수집기 — 최신 트윗 검색"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from backend.config import settings
from backend.services.collectors.base import BaseCollector, make_post
from backend.services.collectors.compliance import remove_pii

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"


def _parse_iso(ts: str) -> datetime:
    """ISO 8601 타임스탬프 → datetime (UTC)."""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc)


def _mock_posts(keyword: str) -> list[dict]:
    now = datetime.now(timezone.utc)
    return [
        make_post(
            platform="x",
            source_account="@mock_user1",
            content=f"[Mock] '{keyword}' X 검색 결과입니다. X_BEARER_TOKEN을 .env에 설정하면 실제 데이터가 수집됩니다.",
            post_url="https://twitter.com/mock_user1/status/1",
            published_at=now,
            likes=12,
            comments=3,
            shares=5,
            follower_count=1200,
            is_mock=True,
        ),
        make_post(
            platform="x",
            source_account="@mock_user2",
            content=f"[Mock] '{keyword}' 관련 두 번째 트윗 예시입니다.",
            post_url="https://twitter.com/mock_user2/status/2",
            published_at=now,
            likes=45,
            comments=8,
            shares=20,
            follower_count=8500,
            is_mock=True,
        ),
    ]


class XTwitterCollector(BaseCollector):
    async def search(self, keyword: str, limit: int = 10) -> list[dict]:
        if not settings.x_bearer_token:
            logger.info("X Bearer Token 없음 — Mock 반환")
            return _mock_posts(keyword)

        # 최대 10건 (Free tier 제한)
        max_results = max(10, min(limit, 100))

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    _SEARCH_URL,
                    headers={"Authorization": f"Bearer {settings.x_bearer_token}"},
                    params={
                        "query": f"{keyword} lang:ko -is:retweet",
                        "max_results": max_results,
                        "tweet.fields": "created_at,public_metrics,author_id",
                        "user.fields": "username,name,public_metrics,created_at",
                        "expansions": "author_id",
                    },
                )

            if resp.status_code == 429:
                logger.warning("X API 요청 한도 초과 — Mock 반환")
                return _mock_posts(keyword)

            if resp.status_code != 200:
                logger.warning("X API 오류: %s %s", resp.status_code, resp.text[:200])
                return _mock_posts(keyword)

            data = resp.json()
            tweets = data.get("data", [])
            users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

            posts: list[dict] = []
            for tweet in tweets:
                author_id = tweet.get("author_id", "")
                user = users.get(author_id, {})
                username = user.get("username", author_id)
                metrics = tweet.get("public_metrics", {})
                user_metrics = user.get("public_metrics", {})

                account_created_at: datetime | None = None
                if user.get("created_at"):
                    account_created_at = _parse_iso(user["created_at"])

                posts.append(make_post(
                    platform="x",
                    source_account=f"@{username}",
                    content=remove_pii(tweet.get("text", "")),
                    post_url=f"https://twitter.com/{username}/status/{tweet['id']}",
                    published_at=_parse_iso(tweet.get("created_at", "")),
                    likes=metrics.get("like_count", 0),
                    comments=metrics.get("reply_count", 0),
                    shares=metrics.get("retweet_count", 0) + metrics.get("quote_count", 0),
                    account_created_at=account_created_at,
                    follower_count=user_metrics.get("followers_count"),
                ))

            return posts[:limit]

        except Exception as e:
            logger.warning("X 수집 실패: %s — Mock 반환", e)
            return _mock_posts(keyword)
