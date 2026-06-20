from pathlib import Path
from unittest.mock import patch

from cardnews.run_log import LogEntry, append_log_entry
from cardnews.review_status import ReviewStatus, save_review_status
import history


def _run(tmp_path: Path, argv: list[str]) -> str:
    captured: list[str] = []
    with (
        patch("sys.argv", ["history.py"] + argv),
        patch("builtins.print", side_effect=lambda *a, **kw: captured.append(" ".join(str(x) for x in a))),
    ):
        history.main(tmp_path)
    return "\n".join(captured)


def test_history_shows_no_entries_message(tmp_path):
    output = _run(tmp_path, ["--no-review"])
    assert "없습니다" in output


def test_history_shows_log_entries(tmp_path):
    path = tmp_path / "run_log.jsonl"
    append_log_entry(
        path,
        LogEntry(timestamp="2026-06-17T00:00:00+00:00", source_id="t-001", status="uploaded", youtube_video_id="yt123"),
    )

    output = _run(tmp_path, ["--no-review"])
    assert "t-001" in output
    assert "uploaded" in output
    assert "yt123" in output


def test_history_filters_by_status(tmp_path):
    path = tmp_path / "run_log.jsonl"
    append_log_entry(path, LogEntry(timestamp="2026-06-17T00:00:00+00:00", source_id="t-001", status="uploaded"))
    append_log_entry(path, LogEntry(timestamp="2026-06-17T01:00:00+00:00", source_id="t-002", status="generation_failed"))

    output = _run(tmp_path, ["--no-review", "--status", "uploaded"])
    assert "t-001" in output
    assert "t-002" not in output


def test_history_shows_current_review(tmp_path):
    save_review_status(
        tmp_path / "review_status.json",
        ReviewStatus(source_id="t-001", message_id="m", channel_id="c", status="pending"),
    )

    output = _run(tmp_path, [])
    assert "t-001" in output
    assert "pending" in output
