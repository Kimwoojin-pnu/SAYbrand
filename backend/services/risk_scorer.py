from datetime import datetime, timezone

SEVERITY_WEIGHTS = {
    "critical": 1.0,
    "high":     0.7,
    "medium":   0.4,
    "low":      0.15,
}

MODULE_WEIGHTS = {"A": 1.0, "B": 0.85, "C": 0.7}
PLATFORM_WEIGHTS = {"instagram": 1.0, "youtube": 0.9, "tiktok": 0.85, "x": 0.8, "naver": 0.7}

_ATTACK_WEIGHTS = {
    "text_uniformity":         0.25,
    "account_cluster":         0.20,
    "account_quality_inverse": 0.20,
    "temporal_cluster":        0.15,
    "cross_platform":          0.10,
    "reaction_uniformity":     0.10,
}
_FLAG_THRESHOLD = 0.6


def recency_weight(detected_at: datetime) -> float:
    now = datetime.now(timezone.utc)
    dt = detected_at if detected_at.tzinfo else detected_at.replace(tzinfo=timezone.utc)
    hours_ago = (now - dt).total_seconds() / 3600
    if hours_ago < 1:
        return 1.0
    elif hours_ago < 6:
        return 0.9
    elif hours_ago < 24:
        return 0.75
    elif hours_ago < 72:
        return 0.5
    elif hours_ago < 168:
        return 0.3
    else:
        return 0.1


def velocity_bonus(engagements_per_hour: float) -> float:
    return min(engagements_per_hour / 1000, 0.3)


def calculate_risk_score(
    severity: str,
    module: str,
    platform: str,
    confidence: float,
    is_organized: bool = False,
    detected_at: datetime | None = None,
    engagements_per_hour: float = 0.0,
    profile=None,               # ProfileLoader.LoadedProfile | None
    executive_priority: int | None = None,
) -> int:
    base = (
        SEVERITY_WEIGHTS.get(severity, 0.4)
        * MODULE_WEIGHTS.get(module, 0.7)
        * PLATFORM_WEIGHTS.get(platform, 0.7)
        * confidence
        * 100
    )

    # 업종별 가중치
    if profile is not None:
        base *= profile.industry_config.get("risk_multiplier", 1.0)

    # 임직원 우선순위 가중치 (Module C)
    if module == "C" and executive_priority is not None:
        exec_multiplier = {1: 1.5, 2: 1.2, 3: 1.0}.get(executive_priority, 1.0)
        base *= exec_multiplier

    if is_organized:
        base = min(base * 1.3, 100)

    r = recency_weight(detected_at) if detected_at else 1.0
    v = velocity_bonus(engagements_per_hour)
    final = base * (r + v)
    return round(min(max(final, 0), 100))


def classify_alert_threshold(risk_score: int, profile=None) -> str:
    """
    업종별 알림 임계값 적용.
    금융업은 45점 이상이면 high, 일반업은 60점 이상이어야 high.
    """
    threshold = 60  # 기본
    if profile is not None:
        threshold = profile.industry_config.get("alert_threshold", 60)

    if risk_score >= 80:
        return "critical"
    if risk_score >= threshold:
        return "high"
    if risk_score >= 35:
        return "medium"
    return "low"


def calculate_overall_score(module_scores: dict) -> float:
    a = module_scores.get("A", 0)
    b = module_scores.get("B", 0)
    c = module_scores.get("C", 0)
    return round(a * 0.40 + b * 0.35 + c * 0.25, 1)


def calculate_attack_score(
    text_similarity_variance: float,       # 0=완전동일, 1=전부다름
    accounts_mutual_follow_ratio: float,   # 공격 계정끼리 맞팔 비율
    posting_time_std_minutes: float,       # 게시 시각 표준편차(분)
    avg_account_age_days: float,
    avg_profile_completeness: float,       # 0~1 (아바타+소개+게시수)
    cross_platform_time_gap_hours: float,  # 플랫폼 간 발화 시간차
    reaction_diversity_score: float,       # 댓글 다양성 0~1
) -> dict:
    # ── 컴포넌트 계산 ──────────────────────────────────────────────────────────
    text_uniformity = 1.0 - text_similarity_variance

    account_cluster = accounts_mutual_follow_ratio

    age_factor = min(avg_account_age_days / 365, 1.0)
    account_quality_inverse = 1.0 - avg_profile_completeness * age_factor

    # 60분 기준 선형 감소, 초과 시 0
    temporal_cluster = max(0.0, 1.0 - posting_time_std_minutes / 60.0)

    if cross_platform_time_gap_hours < 1:
        cross_platform = 1.0
    elif cross_platform_time_gap_hours < 6:
        cross_platform = 0.3
    else:
        cross_platform = 0.0

    reaction_uniformity = 1.0 - reaction_diversity_score

    components = {
        "text_uniformity":         text_uniformity,
        "account_cluster":         account_cluster,
        "account_quality_inverse": account_quality_inverse,
        "temporal_cluster":        temporal_cluster,
        "cross_platform":          cross_platform,
        "reaction_uniformity":     reaction_uniformity,
    }

    # ── attack_score 가중합 ────────────────────────────────────────────────────
    attack_score = round(
        sum(components[k] * _ATTACK_WEIGHTS[k] for k in components), 4
    )

    # ── flags ─────────────────────────────────────────────────────────────────
    flag_names = {
        "text_uniformity":         "text_uniformity",
        "account_cluster":         "account_network",
        "account_quality_inverse": "low_account_quality",
        "temporal_cluster":        "temporal_clustering",
        "cross_platform":          "cross_platform_simultaneous",
        "reaction_uniformity":     "reaction_uniformity",
    }
    flags = [
        flag_names[k]
        for k, v in components.items()
        if v >= _FLAG_THRESHOLD
    ]

    # ── verdict ───────────────────────────────────────────────────────────────
    if attack_score >= 0.7:
        verdict = "organized_attack"
    elif attack_score >= 0.4:
        verdict = "gray_zone"
    else:
        verdict = "legitimate_criticism"

    # ── confidence ────────────────────────────────────────────────────────────
    if attack_score >= 0.75 or attack_score < 0.30:
        confidence = "high"
    elif 0.40 <= attack_score < 0.55:
        confidence = "low"
    else:
        confidence = "medium"

    return {
        "attack_score": attack_score,
        "verdict": verdict,
        "confidence": confidence,
        "flags": flags,
    }
