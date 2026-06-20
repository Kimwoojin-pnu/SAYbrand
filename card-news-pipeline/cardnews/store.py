import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS card_news_publish (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL UNIQUE,
    message_id TEXT NOT NULL DEFAULT '',
    channel_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    video_path TEXT NOT NULL DEFAULT '',
    youtube_video_id TEXT,
    published_at TEXT,
    error_message TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS run_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    source_id TEXT,
    status TEXT NOT NULL,
    video_path TEXT NOT NULL DEFAULT '',
    youtube_video_id TEXT,
    error_message TEXT
);
"""


def db_path(path: Path) -> Path:
    """Derive the SQLite DB file path from a legacy file path or directory."""
    if path.is_dir() or not path.suffix:
        return path / "cardnews.db"
    return path.parent / "cardnews.db"


@contextmanager
def open_db(path: Path):
    """Context manager: open the SQLite DB, ensure schema, yield connection."""
    db = db_path(path)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def tags_to_json(tags: list[str]) -> str:
    return json.dumps(tags, ensure_ascii=False)


def json_to_tags(raw: str) -> list[str]:
    return json.loads(raw) if raw else []
