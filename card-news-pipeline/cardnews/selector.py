from datetime import date, timedelta

from cardnews.models import ThreatRecord


def select_best_candidate(
    records: list[ThreatRecord],
    used_ids: set[str] | None = None,
) -> ThreatRecord | None:
    used_ids = used_ids or set()
    candidates = [r for r in records if r.id not in used_ids]

    if not candidates:
        return None

    today = date.today()

    for days_back in [0, 1, 2, 3]:
        target = today - timedelta(days=days_back)
        pool = [r for r in candidates if r.detected_at == target]
        if pool:
            return max(pool, key=lambda r: r.impact_score)

    # 최근 3일 이내 없으면 전체에서 최고점
    return max(candidates, key=lambda r: r.impact_score)
