from dataclasses import dataclass, field
from pathlib import Path

from cardnews.store import json_to_tags, open_db, tags_to_json


@dataclass
class ReviewStatus:
    source_id: str
    message_id: str
    channel_id: str
    status: str  # "pending" | "approved" | "rejected_final" | "uploaded" | "upload_failed"
    retry_count: int = 0
    title: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    video_path: str = ""
    youtube_video_id: str | None = None
    published_at: str | None = None
    error_message: str | None = None


def save_review_status(path: Path, status: ReviewStatus) -> None:
    with open_db(path) as conn:
        conn.execute(
            """
            INSERT INTO card_news_publish
                (source_id, message_id, channel_id, status, retry_count,
                 title, description, tags, video_path,
                 youtube_video_id, published_at, error_message, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(source_id) DO UPDATE SET
                message_id      = excluded.message_id,
                channel_id      = excluded.channel_id,
                status          = excluded.status,
                retry_count     = excluded.retry_count,
                title           = excluded.title,
                description     = excluded.description,
                tags            = excluded.tags,
                video_path      = excluded.video_path,
                youtube_video_id = excluded.youtube_video_id,
                published_at    = excluded.published_at,
                error_message   = excluded.error_message,
                updated_at      = datetime('now')
            """,
            (
                status.source_id, status.message_id, status.channel_id,
                status.status, status.retry_count,
                status.title, status.description,
                tags_to_json(status.tags), status.video_path,
                status.youtube_video_id, status.published_at, status.error_message,
            ),
        )


def load_review_status(path: Path) -> ReviewStatus | None:
    with open_db(path) as conn:
        row = conn.execute(
            "SELECT * FROM card_news_publish ORDER BY updated_at DESC, id DESC LIMIT 1"
        ).fetchone()

    if row is None:
        return None

    return ReviewStatus(
        source_id=row["source_id"],
        message_id=row["message_id"],
        channel_id=row["channel_id"],
        status=row["status"],
        retry_count=row["retry_count"],
        title=row["title"],
        description=row["description"],
        tags=json_to_tags(row["tags"]),
        video_path=row["video_path"],
        youtube_video_id=row["youtube_video_id"],
        published_at=row["published_at"],
        error_message=row["error_message"],
    )
