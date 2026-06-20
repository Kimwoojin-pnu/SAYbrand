from pathlib import Path

import pytest

from cardnews.store import db_path, open_db


def test_db_path_from_file_path(tmp_path):
    p = tmp_path / "run_log.jsonl"
    assert db_path(p) == tmp_path / "cardnews.db"


def test_db_path_from_directory(tmp_path):
    assert db_path(tmp_path) == tmp_path / "cardnews.db"


def test_open_db_creates_schema(tmp_path):
    with open_db(tmp_path / "run_log.jsonl") as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "card_news_publish" in tables
    assert "run_log" in tables


def test_open_db_creates_parent_dirs(tmp_path):
    nested = tmp_path / "a" / "b" / "run_log.jsonl"
    with open_db(nested) as conn:
        conn.execute("SELECT 1")
    assert (tmp_path / "a" / "b" / "cardnews.db").exists()


def test_open_db_rollback_on_exception(tmp_path):
    path = tmp_path / "run_log.jsonl"
    with pytest.raises(ValueError):
        with open_db(path) as conn:
            conn.execute(
                "INSERT INTO run_log (timestamp, source_id, status) VALUES (?, ?, ?)",
                ("t1", "x", "generated"),
            )
            raise ValueError("force rollback")

    with open_db(path) as conn:
        rows = conn.execute("SELECT * FROM run_log").fetchall()
    assert rows == []


def test_two_paths_same_dir_share_db(tmp_path):
    path_a = tmp_path / "run_log.jsonl"
    path_b = tmp_path / "review_status.json"
    assert db_path(path_a) == db_path(path_b)
