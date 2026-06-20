import os
import re
from datetime import date

import psycopg2

from cardnews.mock_data import load_sample_threats
from cardnews.models import ThreatRecord

_QUERY = """
    SELECT
        id::text,
        COALESCE(threat_type, severity, '위협') AS category,
        COALESCE(
            NULLIF(CASE WHEN ai_analysis LIKE '[Mock]%' THEN NULL ELSE ai_analysis END, ''),
            content_preview
        ) AS summary,
        risk_score::int,
        detected_at::date
    FROM threats
    WHERE content_preview IS NOT NULL
      AND detected_at >= NOW() - INTERVAL '14 days'
      AND severity IN ('critical', 'high', 'medium')
    ORDER BY risk_score DESC NULLS LAST
    LIMIT 20
"""


def _strip_bracket_prefix(text: str) -> str:
    return re.sub(r"^\[.*?\]\s*", "", text).strip()


def load_threats() -> list[ThreatRecord]:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return load_sample_threats()

    try:
        with psycopg2.connect(database_url, options="-c client_encoding=UTF8") as conn:
            with conn.cursor() as cur:
                cur.execute(_QUERY)
                rows = cur.fetchall()

        if not rows:
            return load_sample_threats()

        return [
            ThreatRecord(
                id=str(row[0]),
                category=str(row[1]),
                summary=_strip_bracket_prefix(str(row[2])),
                impact_score=int(row[3]) if row[3] is not None else 5,
                detected_at=row[4] if isinstance(row[4], date) else date.today(),
            )
            for row in rows
        ]
    except Exception:
        return load_sample_threats()
