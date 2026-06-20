from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cardnews.store import open_db


@dataclass
class LogEntry:
    timestamp: str
    source_id: str | None
    status: str
    video_path: str = ""
    youtube_video_id: str | None = None
    error_message: str | None = None


def append_log_entry(path: Path, entry: LogEntry) -> None:
    with open_db(path) as conn:
        conn.execute(
            """
            INSERT INTO run_log (timestamp, source_id, status, video_path, youtube_video_id, error_message)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (entry.timestamp, entry.source_id, entry.status,
             entry.video_path, entry.youtube_video_id, entry.error_message),
        )


def load_log_entries(path: Path) -> list[LogEntry]:
    with open_db(path) as conn:
        rows = conn.execute("SELECT * FROM run_log ORDER BY id ASC").fetchall()

    return [
        LogEntry(
            timestamp=row["timestamp"],
            source_id=row["source_id"],
            status=row["status"],
            video_path=row["video_path"] or "",
            youtube_video_id=row["youtube_video_id"],
            error_message=row["error_message"],
        )
        for row in rows
    ]


def log_event(
    output_dir: Path,
    source_id: str | None,
    status: str,
    video_path: str = "",
    youtube_video_id: str | None = None,
    error_message: str | None = None,
) -> None:
    entry = LogEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        source_id=source_id,
        status=status,
        video_path=video_path,
        youtube_video_id=youtube_video_id,
        error_message=error_message,
    )
    append_log_entry(output_dir / "run_log.jsonl", entry)
