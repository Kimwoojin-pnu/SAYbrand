"""L1 필터 테스트 — keyword_database 기반 재작성 검증"""
import pytest
from backend.services.analyzers.l1_filter import l1_filter


# ── CRITICAL_BYPASS ────────────────────────────────────────────────

class TestCriticalBypass:
    def test_bypass_with_brand_in_text(self):
        result = l1_filter("삼성 전 고객 수백만건유출 발생", brand_keywords=["삼성"])
        assert result["auto_critical"] is True
        assert result["score"] == 1.0
        assert result["severity"] == "critical"
        assert result["pass"] is True
        assert "CRITICAL_BYPASS" in result["matched_categories"]
        assert result["negative_filter_applied"] is False

    def test_bypass_requires_brand_skipped_without_brand(self):
        # CRITICAL_BYPASS requires_brand=True → 브랜드 없으면 트리거 안 됨
        result = l1_filter("수백만건유출 발생 심각")
        assert result["auto_critical"] is False

    def test_bypass_brand_not_present_in_text(self):
        # brand_keywords 제공했지만 텍스트에 없음
        result = l1_filter("수백만건유출 발생", brand_keywords=["삼성"])
        assert result["auto_critical"] is False

    def test_bypass_life_threat_keyword(self):
        result = l1_filter("LG 제품 사망사고 확인됨", brand_keywords=["LG", "엘지"])
        assert result["auto_critical"] is True

    def test_bypass_legal_keyword(self):
        result = l1_filter("기업 압수수색집행 완료", brand_keywords=["기업"])
        assert result["auto_critical"] is True


# ── requires_brand 동작 ────────────────────────────────────────────

class TestRequiresBrand:
    def test_requires_brand_true_with_brand(self):
        # B1: 발암물질 (requires_brand=True)
        result = l1_filter("삼성 제품 발암물질 검출", brand_keywords=["삼성"])
        assert result["pass"] is True
        assert "B1_product_safety_crisis" in result["matched_categories"]

    def test_requires_brand_true_without_brand_skipped(self):
        # requires_brand=True → brand_keywords 없으면 스코어 없음
        result = l1_filter("발암물질 검출 심각한 상황")
        assert "B1_product_safety_crisis" not in result["matched_categories"]

    def test_requires_brand_false_scores_without_brand(self):
        # B4: 불매운동 (requires_brand=True) → 브랜드 있어야 스코어
        # 브랜드 포함 시 매칭됨을 확인
        result = l1_filter("불매운동 boycott 동참해요", brand_keywords=["브랜드"])
        # B4 weight=0.70, 텍스트에 "브랜드" 없으므로 brand_ok=False → 매칭 안 됨
        # brand_keywords에 "브랜드"를 줬지만 텍스트에 "브랜드"가 없어 brand_ok=False
        assert "B4_organized_attack_bot" not in result["matched_categories"]
        # A1_impersonation_account(requires_brand=False)는 키워드 없으므로 pass=False
        assert result["pass"] is False

    def test_requires_brand_false_a1_impersonation(self):
        # A1: 공식계정 (requires_brand=False)
        result = l1_filter("공식계정입니다 팔로우해주세요")
        assert result["pass"] is True
        assert "A1_impersonation_account" in result["matched_categories"]

    def test_empty_brand_keywords_treated_as_none(self):
        # brand_keywords=[] → brand_ok=False
        result = l1_filter("삼성 발암물질 검출", brand_keywords=[])
        assert "B1_product_safety_crisis" not in result["matched_categories"]


# ── 음성 필터 (Negative Filter) ────────────────────────────────────

class TestNegativeFilter:
    def test_negative_keyword_reduces_score_40_percent(self):
        # B5: 환불거부 (weight=0.70, requires_brand=True)
        # 음성: "공식발표"
        # 텍스트에 brand keyword 포함해야 brand_ok=True
        result_clean = l1_filter("브랜드 환불거부 사태", brand_keywords=["브랜드"])
        result_neg = l1_filter("공식발표 브랜드 환불거부 사태", brand_keywords=["브랜드"])

        assert result_neg["negative_filter_applied"] is True
        assert result_clean["negative_filter_applied"] is False
        assert result_neg["score"] == pytest.approx(result_clean["score"] * 0.60, rel=0.01)

    def test_negative_filter_not_applied_when_no_threat(self):
        # 위협 없으면 음성 필터도 적용 안 됨
        result = l1_filter("공식발표 좋은 소식입니다")
        assert result["negative_filter_applied"] is False
        assert result["pass"] is False

    def test_negative_filter_can_drop_below_threshold(self):
        # B6 weight=0.40, * 0.60 = 0.24 → pass threshold(0.10) 이상이지만 medium 미만
        result = l1_filter("공식발표 브랜드 서비스 실망 별로", brand_keywords=["브랜드"])
        assert result["negative_filter_applied"] is True
        assert result["score"] == pytest.approx(0.40 * 0.60, rel=0.01)
        assert result["pass"] is True  # 0.24 >= 0.10


# ── 무위협 (Safe Content) ──────────────────────────────────────────

class TestSafeContent:
    def test_completely_safe_text(self):
        result = l1_filter("오늘 날씨가 맑고 기분이 좋아요", brand_keywords=["브랜드"])
        assert result["pass"] is False
        assert result["score"] == 0.0
        assert result["severity"] is None
        assert result["matched_categories"] == []
        assert result["auto_critical"] is False

    def test_empty_text(self):
        result = l1_filter("")
        assert result["pass"] is False
        assert result["score"] == 0.0

    def test_no_brand_keywords_with_brand_required_categories_only(self):
        # 모든 매칭 카테고리가 requires_brand=True인 경우
        result = l1_filter("발암물질 리콜 파산")  # B1, B3 — 모두 requires_brand=True
        assert result["pass"] is False
        assert result["score"] == 0.0


# ── 점수 누적 및 클램프 ────────────────────────────────────────────

class TestScoreAccumulation:
    def test_multiple_categories_accumulate_score(self):
        # A1(0.90, requires_brand=False) 단독 매칭 확인
        # B4(requires_brand=True)는 브랜드 없으면 매칭 안 됨
        result = l1_filter("공식계정 불매운동 boycott")
        assert "A1_impersonation_account" in result["matched_categories"]
        assert result["score"] == pytest.approx(0.90)

    def test_score_clamped_at_1(self):
        # 다수 고가중치 카테고리 매칭 → 1.0 초과 불가
        text = "공식계정 불매운동 boycott 해킹 내부자거래 갑질"
        result = l1_filter(text, brand_keywords=["기업"])
        assert result["score"] <= 1.0

    def test_single_high_weight_match(self):
        # A1 단독 (weight=0.90, requires_brand=False)
        result = l1_filter("공식계정입니다")
        assert result["score"] == pytest.approx(0.90)
        assert result["severity"] == "critical"  # 0.90 >= 0.70


# ── 심각도 임계값 ──────────────────────────────────────────────────

class TestSeverityThresholds:
    def test_critical_severity_above_070(self):
        # A1 weight=0.90, requires_brand=False → critical (0.90 >= 0.70)
        result = l1_filter("공식계정입니다")
        assert result["severity"] == "critical"

    def test_high_severity_045_to_070(self):
        # B5 weight=0.70, 음성 필터 적용 → 0.70*0.60=0.42 → medium
        # B9 weight=0.65 단독 (requires_brand=True) + brand
        result = l1_filter("브랜드 경쟁사가더낫다 비교 비추", brand_keywords=["브랜드"])
        assert result["severity"] in ("medium", "high")

    def test_medium_severity_025_to_045(self):
        # B6 weight=0.40, requires_brand=True
        result = l1_filter("브랜드 서비스 실망 별로", brand_keywords=["브랜드"])
        assert result["severity"] == "medium"
        assert result["score"] == pytest.approx(0.40)

    def test_low_severity_010_to_025(self):
        # B6(0.40) + 음성 필터 → 0.24 → low
        result = l1_filter("공식발표 브랜드 서비스 실망 별로", brand_keywords=["브랜드"])
        assert result["severity"] == "low"
        assert result["score"] == pytest.approx(0.24, rel=0.01)

    def test_none_severity_below_threshold(self):
        result = l1_filter("오늘 맛있는 점심을 먹었다", brand_keywords=["브랜드"])
        assert result["severity"] is None
        assert result["pass"] is False


# ── 반환값 구조 ────────────────────────────────────────────────────

class TestReturnStructure:
    def test_all_keys_present(self):
        result = l1_filter("테스트 텍스트")
        expected_keys = {
            "pass", "score", "severity",
            "auto_critical", "matched_categories", "negative_filter_applied",
        }
        assert set(result.keys()) == expected_keys

    def test_score_in_valid_range(self):
        for text in ["불매운동", "발암물질", "공식계정", "안녕하세요"]:
            result = l1_filter(text, brand_keywords=["브랜드"])
            assert 0.0 <= result["score"] <= 1.0

    def test_matched_categories_is_list(self):
        result = l1_filter("안녕하세요")
        assert isinstance(result["matched_categories"], list)
