"""플랫폼별 바이럴 계수로 콘텐츠 도달 범위 추정"""
from __future__ import annotations

PLATFORM_VIRAL_COEF: dict[str, float] = {
    "instagram": 3.5,
    "youtube":   8.0,
    "tiktok":    12.0,
    "x":         4.0,
    "naver":     1.5,
    "community": 2.0,
}

_ENGAGEMENT_BASELINE: dict[str, int] = {
    "instagram": 500,
    "youtube":   2000,
    "tiktok":    1000,
    "x":         300,
    "naver":     200,
    "community": 150,
}


def estimate_reach(platform: str, engagements: int = 0) -> int:
    coef = PLATFORM_VIRAL_COEF.get(platform, 2.0)
    base = _ENGAGEMENT_BASELINE.get(platform, 200)
    raw = max(engagements, base) * coef
    return int(raw)


def format_reach(reach: int) -> str:
    if reach >= 1_000_000:
        return f"{reach / 1_000_000:.1f}M"
    if reach >= 1_000:
        return f"{reach / 1_000:.1f}K"
    return str(reach)
