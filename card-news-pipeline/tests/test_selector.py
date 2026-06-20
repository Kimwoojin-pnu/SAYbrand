from datetime import date

from cardnews.models import ThreatRecord
from cardnews.selector import select_best_candidate

RECORDS = [
    ThreatRecord(id="a", detected_at=date(2026, 6, 1), category="cat", summary="요약 A", impact_score=5),
    ThreatRecord(id="b", detected_at=date(2026, 6, 2), category="cat", summary="요약 B", impact_score=9),
    ThreatRecord(id="c", detected_at=date(2026, 6, 3), category="cat", summary="요약 C", impact_score=7),
]


def test_select_best_candidate_returns_highest_impact_score():
    result = select_best_candidate(RECORDS)

    assert result is not None
    assert result.id == "b"


def test_select_best_candidate_skips_used_ids():
    result = select_best_candidate(RECORDS, used_ids={"b"})

    assert result is not None
    assert result.id == "c"


def test_select_best_candidate_returns_none_when_no_candidates_left():
    result = select_best_candidate(RECORDS, used_ids={"a", "b", "c"})

    assert result is None
