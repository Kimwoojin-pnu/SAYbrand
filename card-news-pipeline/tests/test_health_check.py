from unittest.mock import patch

from cardnews.run_log import LogEntry, append_log_entry, log_event
from health_check import has_uploaded_today, main


def test_has_uploaded_today_true_when_uploaded_entry_exists_for_today(tmp_path):
    log_event(tmp_path, source_id="threat-003", status="uploaded", youtube_video_id="abc123")

    assert has_uploaded_today(tmp_path) is True


def test_has_uploaded_today_false_when_no_entries(tmp_path):
    assert has_uploaded_today(tmp_path) is False


def test_has_uploaded_today_false_when_only_old_entries(tmp_path):
    append_log_entry(
        tmp_path / "run_log.jsonl",
        LogEntry(timestamp="2000-01-01T00:00:00+00:00", source_id="threat-001", status="uploaded"),
    )

    assert has_uploaded_today(tmp_path) is False


def test_main_sends_alert_when_no_upload_today(capsys):
    with patch("health_check.has_uploaded_today", return_value=False), \
            patch("health_check.send_alert") as mock_alert:
        main()

    mock_alert.assert_called_once()
    captured = capsys.readouterr()
    assert "오늘 업로드된 카드뉴스가 없습니다" in captured.out


def test_main_skips_alert_when_upload_today(capsys):
    with patch("health_check.has_uploaded_today", return_value=True), \
            patch("health_check.send_alert") as mock_alert:
        main()

    mock_alert.assert_not_called()
    captured = capsys.readouterr()
    assert "정상적으로 업로드되었습니다" in captured.out
