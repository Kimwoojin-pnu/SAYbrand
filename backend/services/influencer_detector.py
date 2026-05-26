"""인플루언서 영향력 점수 계산"""
from __future__ import annotations

PLATFORM_FOLLOWER_WEIGHT: dict[str, float] = {
    "instagram": 1.0,
    "youtube":   1.5,
    "tiktok":    1.2,
    "x":         0.9,
    "naver":     0.6,
    "community": 0.5,
}


def calculate_influence_score(
    platform: str,
    follower_count: int = 0,
    avg_engagement_rate: float = 0.0,
    post_frequency: float = 1.0,
) -> float:
    weight = PLATFORM_FOLLOWER_WEIGHT.get(platform, 0.7)
    follower_score = min(follower_count / 1_000_000, 1.0) * 40
    engagement_score = min(avg_engagement_rate / 0.10, 1.0) * 40
    freq_score = min(post_frequency / 10.0, 1.0) * 20
    return round((follower_score + engagement_score + freq_score) * weight, 2)


def classify_influencer_tier(score: float) -> str:
    if score >= 70:
        return "mega"
    if score >= 40:
        return "macro"
    if score >= 15:
        return "micro"
    return "nano"
