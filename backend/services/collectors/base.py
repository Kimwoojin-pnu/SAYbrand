"""수집기 공통 인터페이스"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawPost:
    platform: str
    source_account: str
    content: str
    post_url: str
    published_at: datetime
    likes: int = 0
    comments: int = 0
    shares: int = 0
    follower_count: int = 0
    account_age_days: int = 0
    image_urls: list[str] = field(default_factory=list)
    is_mock: bool = False


def make_post(
    platform: str,
    source_account: str,
    content: str,
    post_url: str,
    published_at: datetime,
    likes: int = 0,
    comments: int = 0,
    shares: int = 0,
    account_created_at: datetime | None = None,
    follower_count: int | None = None,
    is_mock: bool = False,
) -> dict:
    """수집기 반환 딕셔너리를 통일된 형식으로 생성한다."""
    age_days = 0
    if account_created_at:
        delta = datetime.utcnow() - account_created_at.replace(tzinfo=None)
        age_days = max(0, delta.days)

    return {
        "platform": platform,
        "source_account": source_account,
        "content": content,
        "post_url": post_url,
        "published_at": published_at,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "account_created_at": account_created_at,
        "follower_count": follower_count,
        "account_age_days": age_days,
        "is_mock": is_mock,
    }


class BaseCollector(ABC):
    @abstractmethod
    async def search(
        self,
        keyword: str,
        limit: int = 25,
        days_back: int = 7,
    ) -> list[dict]:
        """
        키워드로 콘텐츠를 검색한다.

        Returns:
            make_post() 형식의 딕셔너리 리스트.
            API 키 없으면 is_mock=True인 Mock 데이터 반환.
        """
