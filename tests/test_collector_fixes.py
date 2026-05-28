"""
Fix 검증 테스트:
1. naver.py _to_utc — timezone-aware datetime을 올바르게 변환
2. l1_filter_with_profile — display_name만 있고 aliases 없을 때 brand_mentioned=True
3. community_kr.py — 클리앙/루리웹 HTML 구조에 맞는 파서 동작
"""
import pytest
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field


# ── Fix 1: naver _to_utc ──────────────────────────────────────────────────────

class TestNaverToUtc:
    def _to_utc(self, dt):
        from backend.services.collectors.naver import _to_utc
        return _to_utc(dt)

    def test_naive_datetime_treated_as_utc(self):
        naive = datetime(2026, 5, 1, 12, 0, 0)
        result = self._to_utc(naive)
        assert result.tzinfo is not None
        assert result == datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_utc_aware_stays_utc(self):
        aware = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = self._to_utc(aware)
        assert result == aware

    def test_kst_aware_converted_correctly(self):
        """KST(UTC+9)를 UTC로 변환하면 9시간 감소해야 함."""
        from datetime import timezone as tz
        kst = timezone(timedelta(hours=9))
        kst_dt = datetime(2026, 5, 1, 21, 0, 0, tzinfo=kst)  # KST 21:00 = UTC 12:00
        result = self._to_utc(kst_dt)
        assert result == datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_replace_was_wrong_but_to_utc_is_correct(self):
        """이전 replace()는 KST datetime을 잘못 처리했음 — 이제 정상."""
        from datetime import timezone as tz
        kst = timezone(timedelta(hours=9))
        kst_dt = datetime(2026, 5, 1, 21, 0, 0, tzinfo=kst)
        cutoff = datetime(2026, 5, 1, 13, 0, 0, tzinfo=timezone.utc)

        # 옛 방식: replace는 timezone만 덮어써서 21:00 UTC로 만들어 버림 → cutoff(13:00) 초과 → 통과
        old_way = kst_dt.replace(tzinfo=timezone.utc)
        assert old_way >= cutoff  # 잘못된 동작 (통과해선 안 되는 케이스)

        # 새 방식: 21:00 KST → 12:00 UTC → cutoff(13:00) 미만 → 필터링
        new_way = self._to_utc(kst_dt)
        assert new_way < cutoff  # 올바른 동작


# ── Fix 2: l1_filter_with_profile display_name brand_mentioned ───────────────

@dataclass
class MockProfile:
    profile_id: int = 1
    display_name: str = "스타벅스"
    industry: str = "food"
    logo_url: str | None = None
    profile_type: str = "company"
    aliases: list = field(default_factory=list)  # 비어있음
    official_handles: dict = field(default_factory=dict)
    executives: list = field(default_factory=list)
    search_keywords: list = field(default_factory=lambda: ["스타벅스"])
    industry_config: dict = field(default_factory=lambda: {
        "risk_multiplier": 1.2,
        "alert_threshold": 50,
        "sensitive_keywords": ["식중독", "이물질", "리콜", "발암", "불량", "유해"],
    })


class TestL1FilterWithProfileDisplayName:
    @pytest.mark.asyncio
    async def test_display_name_only_brand_mentioned_true(self):
        """aliases가 비어있어도 display_name이 텍스트에 있으면 brand_mentioned=True."""
        from backend.services.analyzers.l1_filter import l1_filter_with_profile
        profile = MockProfile()  # aliases=[]

        result = await l1_filter_with_profile(
            content="스타벅스 불매운동 확산 중 소비자 반발",
            account_name="익명유저",
            profile=profile,
        )
        assert result["brand_mentioned"] is True
        assert result["pass"] is True

    @pytest.mark.asyncio
    async def test_display_name_triggers_requires_brand_categories(self):
        """display_name만으로 requires_brand=True 카테고리가 활성화되어야 함."""
        from backend.services.analyzers.l1_filter import l1_filter_with_profile
        profile = MockProfile()

        result = await l1_filter_with_profile(
            content="스타벅스 환불거부 갑질 사건 최악",
            account_name="클리앙유저",
            profile=profile,
        )
        assert result["brand_mentioned"] is True
        assert result["pass"] is True
        assert result["score"] > 0

    @pytest.mark.asyncio
    async def test_no_brand_in_text_still_false(self):
        """텍스트에 브랜드명 없으면 brand_mentioned=False."""
        from backend.services.analyzers.l1_filter import l1_filter_with_profile
        profile = MockProfile()

        result = await l1_filter_with_profile(
            content="환불거부 갑질 사건",  # 스타벅스 없음
            account_name="익명유저",
            profile=profile,
        )
        assert result["brand_mentioned"] is False

    @pytest.mark.asyncio
    async def test_display_name_not_double_counted_when_in_aliases(self):
        """display_name이 이미 aliases에 있으면 중복 추가 안 함."""
        from backend.services.analyzers.l1_filter import l1_filter_with_profile

        @dataclass
        class ProfileWithAlias:
            profile_id: int = 1
            display_name: str = "스타벅스"
            industry: str = "food"
            logo_url: str | None = None
            profile_type: str = "company"
            aliases: list = field(default_factory=lambda: [("스타벅스", 1.0)])
            official_handles: dict = field(default_factory=dict)
            executives: list = field(default_factory=list)
            search_keywords: list = field(default_factory=lambda: ["스타벅스"])
            industry_config: dict = field(default_factory=lambda: {
                "risk_multiplier": 1.0, "alert_threshold": 60, "sensitive_keywords": [],
            })

        profile = ProfileWithAlias()
        result = await l1_filter_with_profile(
            content="스타벅스 환불거부",
            account_name="유저",
            profile=profile,
        )
        # brand_score = 1.0 (중복 없이 한 번만 카운트)
        assert result["brand_mentioned"] is True
        assert result["matched_aliases"] == ["스타벅스"]


# ── Fix 3: community_kr 파서 — 실제 HTML 구조 ────────────────────────────────

CLIEN_MOCK_HTML = """
<html><body>
<div class="list_item">
  <a class="subject_fixed" href="/service/board/park/12345678?q=test">스타벅스 환불 거부 사례 공유</a>
  <span class="list_time">2026-05-28 10:16</span>
</div>
<div class="list_item">
  <a class="subject_fixed" href="/service/board/park/87654321?q=test">스타벅스 갑질 논란 확산</a>
  <span class="list_time">2026-05-27 18:30</span>
</div>
</body></html>
"""

RULIWEB_MOCK_HTML = """
<html><body>
<div class="search_result_item">
  <a class="title text_over" href="https://bbs.ruliweb.com/news/read/111111">스타벅스 불매운동 시작됐나</a>
  <span class="time">2026.05.28</span>
</div>
<div class="search_result_item">
  <a class="title text_over" href="https://bbs.ruliweb.com/news/read/222222">스타벅스 최악의 서비스 후기</a>
  <span class="time">2026.05.27</span>
</div>
</body></html>
"""


class TestCommunityKrParser:
    def _get_collector(self):
        from backend.services.collectors.community_kr import KoreanCommunityCollector
        return KoreanCommunityCollector()

    def test_clien_selector_parses_titles(self):
        collector = self._get_collector()
        site = collector.SITES["clien"]
        posts = collector._parse_posts(
            CLIEN_MOCK_HTML, site, "스타벅스",
            base_url="https://www.clien.net",
            platform="클리앙",
            limit=10,
        )
        assert len(posts) == 2
        assert "스타벅스 환불 거부" in posts[0]["content"]
        assert posts[0]["post_url"].startswith("https://www.clien.net/service/board")

    def test_ruliweb_selector_parses_titles(self):
        collector = self._get_collector()
        site = collector.SITES["ruliweb"]
        posts = collector._parse_posts(
            RULIWEB_MOCK_HTML, site, "스타벅스",
            base_url="https://bbs.ruliweb.com",
            platform="루리웹",
            limit=10,
        )
        assert len(posts) == 2
        assert "스타벅스 불매운동" in posts[0]["content"]
        assert posts[0]["post_url"] == "https://bbs.ruliweb.com/news/read/111111"

    def test_no_keyword_title_filter(self):
        """키워드가 제목에 없어도 수집된다 (서버사이드 검색이 이미 필터링함)."""
        html = """
        <html><body>
        <div class="list_item">
          <a class="subject_fixed" href="/service/board/park/99">이 글은 제목에 브랜드 없음</a>
          <span class="list_time">2026-05-28 10:00</span>
        </div>
        </body></html>
        """
        collector = self._get_collector()
        site = collector.SITES["clien"]
        posts = collector._parse_posts(
            html, site, "스타벅스",
            base_url="https://www.clien.net",
            platform="클리앙",
            limit=10,
        )
        # 이전 코드는 keyword not in title → 0건. 수정 후는 1건
        assert len(posts) == 1

    def test_date_parsing_standard_format(self):
        collector = self._get_collector()
        dt = collector._parse_date("2026.05.28")
        assert dt.year == 2026
        assert dt.month == 5
        assert dt.day == 28

    def test_date_parsing_dash_format(self):
        collector = self._get_collector()
        dt = collector._parse_date("2026-05-27 18:30")
        assert dt.year == 2026
        assert dt.month == 5
        assert dt.day == 27

    def test_only_clien_and_ruliweb_in_sites(self):
        """검증된 사이트만 SITES에 남아 있어야 함."""
        collector = self._get_collector()
        assert set(collector.SITES.keys()) == {"clien", "ruliweb"}
