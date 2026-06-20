from datetime import date

from cardnews.models import ThreatRecord
from cardnews.scripter import generate_script

RECORD = ThreatRecord(
    id="threat-099",
    detected_at=date(2026, 6, 7),
    category="허위 리뷰 확산",
    summary="테스트용 요약 내용입니다.",
    impact_score=8,
)


def test_generate_script_links_back_to_source_record():
    script = generate_script(RECORD)

    assert script.source_id == RECORD.id


def test_generate_script_produces_slides_that_use_the_summary():
    script = generate_script(RECORD)

    assert len(script.slides) >= 3
    assert any(RECORD.summary in slide.body for slide in script.slides)
    assert all(slide.headline and slide.body for slide in script.slides)


def test_generate_script_includes_category_in_title_and_tags():
    script = generate_script(RECORD)

    assert RECORD.category in script.title
    assert "브랜드리스크" in script.tags
