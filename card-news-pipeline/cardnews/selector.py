from cardnews.models import ThreatRecord


def select_best_candidate(
    records: list[ThreatRecord],
    used_ids: set[str] | None = None,
) -> ThreatRecord | None:
    used_ids = used_ids or set()
    candidates = [record for record in records if record.id not in used_ids]

    if not candidates:
        return None

    return max(candidates, key=lambda record: record.impact_score)
