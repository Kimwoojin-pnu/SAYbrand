from backend.services.risk_scorer import (
    calculate_attack_score,
    calculate_overall_score,
    calculate_risk_score,
)


# ── 기존 테스트 (recency/velocity default=1.0/0.0 이므로 결과 동일) ───────────

def test_critical_instagram():
    score = calculate_risk_score("critical", "A", "instagram", 0.95)
    assert score == round(1.0 * 1.0 * 1.0 * 0.95 * 100)


def test_high_youtube():
    score = calculate_risk_score("high", "B", "youtube", 0.87)
    assert score == round(0.7 * 0.85 * 0.9 * 0.87 * 100)


def test_organized_multiplier():
    normal = calculate_risk_score("high", "B", "x", 0.8)
    organized = calculate_risk_score("high", "B", "x", 0.8, is_organized=True)
    assert organized > normal
    assert organized <= 100


def test_organized_cap_at_100():
    score = calculate_risk_score("critical", "A", "instagram", 1.0, is_organized=True)
    assert score == 100


def test_overall_formula():
    scores = {"A": 72.0, "B": 55.0, "C": 48.0}
    overall = calculate_overall_score(scores)
    expected = round(72.0 * 0.40 + 55.0 * 0.35 + 48.0 * 0.25, 1)
    assert overall == expected


def test_missing_module_defaults_to_zero():
    overall = calculate_overall_score({"A": 50.0})
    assert overall == round(50.0 * 0.40, 1)


# ── calculate_attack_score 신규 테스트 ───────────────────────────────────────

def test_attack_organized():
    """텍스트 거의 동일 + 신규 계정 + 동시 게시 → organized_attack"""
    result = calculate_attack_score(
        text_similarity_variance=0.05,      # 거의 동일 → text_uniformity=0.95
        accounts_mutual_follow_ratio=0.85,  # 계정 간 밀집 연결
        posting_time_std_minutes=5,         # temporal_cluster=max(0,1-5/60)≈0.917
        avg_account_age_days=30,            # 신규 계정
        avg_profile_completeness=0.1,       # 프로필 미비
        cross_platform_time_gap_hours=0.5,  # 동시 발화 → 1.0
        reaction_diversity_score=0.1,       # 반응 획일적
    )
    assert result["verdict"] == "organized_attack"
    assert result["attack_score"] >= 0.7
    assert result["confidence"] == "high"
    assert "text_uniformity" in result["flags"]
    assert "account_network" in result["flags"]
    assert "temporal_clustering" in result["flags"]


def test_attack_gray_zone():
    """중간 수치 → gray_zone"""
    result = calculate_attack_score(
        text_similarity_variance=0.5,       # 절반 유사 → text_uniformity=0.5
        accounts_mutual_follow_ratio=0.4,   # 부분 연결
        posting_time_std_minutes=30,        # temporal_cluster=max(0,1-30/60)=0.5
        avg_account_age_days=180,           # 6개월 계정
        avg_profile_completeness=0.5,       # 절반 완성
        cross_platform_time_gap_hours=3.0,  # 3시간 차 → 0.3
        reaction_diversity_score=0.5,       # 반응 보통
    )
    assert result["verdict"] == "gray_zone"
    assert 0.4 <= result["attack_score"] < 0.7
    assert result["confidence"] == "low"


def test_attack_legitimate():
    """텍스트 다양 + 오래된 완성 계정 + 분산 패턴 → legitimate_criticism"""
    result = calculate_attack_score(
        text_similarity_variance=0.9,       # 각자 다른 글 → text_uniformity=0.1
        accounts_mutual_follow_ratio=0.05,  # 연결 거의 없음
        posting_time_std_minutes=120,       # temporal_cluster=max(0,1-120/60)=0
        avg_account_age_days=500,           # 오래된 계정
        avg_profile_completeness=0.9,       # 완성된 프로필
        cross_platform_time_gap_hours=12,   # 시간차 큼 → 0.0
        reaction_diversity_score=0.9,       # 반응 다양
    )
    assert result["verdict"] == "legitimate_criticism"
    assert result["attack_score"] < 0.4
    assert result["confidence"] == "high"
    assert result["flags"] == []


def test_temporal_cluster_formula():
    """max(0, 1 - std/60) 공식 검증"""
    # std=0 → 1.0
    r0 = calculate_attack_score(0.5, 0.5, 0, 365, 0.5, 6, 0.5)
    # std=30 → 0.5
    r30 = calculate_attack_score(0.5, 0.5, 30, 365, 0.5, 6, 0.5)
    # std=60 → 0.0
    r60 = calculate_attack_score(0.5, 0.5, 60, 365, 0.5, 6, 0.5)
    # std=120 → 0.0 (초과도 0)
    r120 = calculate_attack_score(0.5, 0.5, 120, 365, 0.5, 6, 0.5)

    assert r0["attack_score"] > r30["attack_score"]
    assert r30["attack_score"] > r60["attack_score"]
    assert r60["attack_score"] == r120["attack_score"]  # 60분 초과는 모두 동일


def test_cross_platform_thresholds():
    """플랫폼 간 시간차 임계값 검증"""
    under_1h = calculate_attack_score(0.5, 0.5, 30, 180, 0.5, 0.5, 0.5)
    under_6h = calculate_attack_score(0.5, 0.5, 30, 180, 0.5, 3.0, 0.5)
    over_6h  = calculate_attack_score(0.5, 0.5, 30, 180, 0.5, 10.0, 0.5)

    assert under_1h["attack_score"] > under_6h["attack_score"]
    assert under_6h["attack_score"] > over_6h["attack_score"]
