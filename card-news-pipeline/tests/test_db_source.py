from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from cardnews.db_source import load_threats
from cardnews.models import ThreatRecord


def test_load_threats_falls_back_to_mock_when_no_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    records = load_threats()

    assert len(records) > 0
    assert all(isinstance(r, ThreatRecord) for r in records)


def test_load_threats_queries_db_when_database_url_set(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")

    fake_rows = [
        ("threat-db-1", "HIGH", "SNS에서 부정 리뷰가 확산되고 있습니다.", 8, date(2026, 6, 15)),
        ("threat-db-2", "MEDIUM", "커뮤니티에서 불만 게시글이 공유되고 있습니다.", 5, date(2026, 6, 14)),
    ]

    mock_cursor = MagicMock()
    mock_cursor.__enter__.return_value = mock_cursor
    mock_cursor.fetchall.return_value = fake_rows

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    with patch("cardnews.db_source.psycopg2.connect", return_value=mock_conn):
        records = load_threats()

    assert len(records) == 2
    assert records[0].id == "threat-db-1"
    assert records[0].category == "HIGH"
    assert records[0].summary == "SNS에서 부정 리뷰가 확산되고 있습니다."
    assert records[0].impact_score == 8
    assert records[0].detected_at == date(2026, 6, 15)


def test_load_threats_falls_back_to_mock_on_db_error(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")

    with patch("cardnews.db_source.psycopg2.connect", side_effect=Exception("connection refused")):
        records = load_threats()

    assert len(records) > 0  # mock fallback


def test_load_threats_falls_back_to_mock_when_db_returns_empty(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")

    mock_cursor = MagicMock()
    mock_cursor.__enter__.return_value = mock_cursor
    mock_cursor.fetchall.return_value = []

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    with patch("cardnews.db_source.psycopg2.connect", return_value=mock_conn):
        records = load_threats()

    assert len(records) > 0  # mock fallback when DB has no recent threats
