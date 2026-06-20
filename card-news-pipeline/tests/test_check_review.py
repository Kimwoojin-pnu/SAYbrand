from pathlib import Path
from unittest.mock import MagicMock, patch

import requests
from googleapiclient.errors import HttpError

from cardnews.models import CardNewsScript, Slide
from cardnews.orchestrator import GenerationResult
from cardnews.review_status import ReviewStatus, load_review_status, save_review_status
from cardnews.run_log import load_log_entries
from cardnews.video import FFmpegNotFoundError
from cardnews.youtube_upload import YouTubeCredentialsError
from check_review import process_review


def _sample_script(source_id: str = "threat-003") -> CardNewsScript:
    return CardNewsScript(
        source_id=source_id,
        title="제목",
        slides=[Slide(headline="h", body="b")],
        description="설명",
        tags=["태그"],
    )


def test_process_review_no_status_file(tmp_path, capsys):
    process_review(tmp_path)

    captured = capsys.readouterr()
    assert "검수 대기 중인 카드뉴스가 없습니다" in captured.out


def test_process_review_already_resolved(tmp_path, capsys):
    status_path = tmp_path / "review_status.json"
    save_review_status(
        status_path,
        ReviewStatus(source_id="threat-003", message_id="m", channel_id="c", status="approved", retry_count=0),
    )

    process_review(tmp_path)

    captured = capsys.readouterr()
    assert "이미 처리된 검수입니다" in captured.out


def test_process_review_pending_reaction(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    status_path = tmp_path / "review_status.json"
    save_review_status(
        status_path,
        ReviewStatus(source_id="threat-003", message_id="m", channel_id="c", status="pending", retry_count=0),
    )

    with patch("check_review.check_reaction", return_value="pending"):
        process_review(tmp_path)

    captured = capsys.readouterr()
    assert "아직 검수 반응이 없습니다" in captured.out
    assert load_review_status(status_path).status == "pending"


def test_process_review_approved(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    monkeypatch.delenv("YOUTUBE_CLIENT_ID", raising=False)
    monkeypatch.delenv("YOUTUBE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("YOUTUBE_REFRESH_TOKEN", raising=False)
    status_path = tmp_path / "review_status.json"
    save_review_status(
        status_path,
        ReviewStatus(source_id="threat-003", message_id="m", channel_id="c", status="pending", retry_count=0),
    )

    with patch("check_review.check_reaction", return_value="approved"):
        process_review(tmp_path)

    captured = capsys.readouterr()
    assert "승인되었습니다" in captured.out
    assert load_review_status(status_path).status == "approved"


def test_process_review_rejected_retries_with_next_candidate(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    status_path = tmp_path / "review_status.json"
    save_review_status(
        status_path,
        ReviewStatus(source_id="threat-003", message_id="m", channel_id="c", status="pending", retry_count=0),
    )

    next_script = _sample_script("threat-004")
    next_result = GenerationResult(script=next_script, slide_paths=[], video_path=tmp_path / "threat-004.mp4")

    with patch("check_review.check_reaction", return_value="rejected"), \
            patch("check_review.generate_video", return_value=next_result) as mock_generate, \
            patch(
                "check_review.request_review",
                return_value=ReviewStatus(
                    source_id="threat-004", message_id="m2", channel_id="c2", status="pending", retry_count=0
                ),
            ):
        process_review(tmp_path)

    mock_generate.assert_called_once_with(tmp_path, used_ids={"threat-003"})
    captured = capsys.readouterr()
    assert "threat-004" in captured.out

    new_status = load_review_status(status_path)
    assert new_status.source_id == "threat-004"
    assert new_status.retry_count == 1


def test_process_review_rejected_after_retry_marks_final(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    status_path = tmp_path / "review_status.json"
    save_review_status(
        status_path,
        ReviewStatus(source_id="threat-004", message_id="m2", channel_id="c2", status="pending", retry_count=1),
    )

    with patch("check_review.check_reaction", return_value="rejected"):
        process_review(tmp_path)

    captured = capsys.readouterr()
    assert "발행하지 않습니다" in captured.out
    assert load_review_status(status_path).status == "rejected_final"


def test_process_review_rejected_no_more_candidates(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    status_path = tmp_path / "review_status.json"
    save_review_status(
        status_path,
        ReviewStatus(source_id="threat-003", message_id="m", channel_id="c", status="pending", retry_count=0),
    )

    with patch("check_review.check_reaction", return_value="rejected"), \
            patch("check_review.generate_video", return_value=None):
        process_review(tmp_path)

    captured = capsys.readouterr()
    assert "다음 후보 소재가 없어" in captured.out
    assert load_review_status(status_path).status == "rejected_final"


def test_process_review_check_reaction_network_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    status_path = tmp_path / "review_status.json"
    save_review_status(
        status_path,
        ReviewStatus(source_id="threat-003", message_id="m", channel_id="c", status="pending", retry_count=0),
    )

    with patch("check_review.check_reaction", side_effect=requests.exceptions.RequestException("boom")):
        process_review(tmp_path)

    captured = capsys.readouterr()
    assert "Discord 반응 조회에 실패했습니다" in captured.out
    assert load_review_status(status_path).status == "pending"


def test_process_review_rejected_retry_request_review_network_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    status_path = tmp_path / "review_status.json"
    save_review_status(
        status_path,
        ReviewStatus(source_id="threat-003", message_id="m", channel_id="c", status="pending", retry_count=0),
    )

    next_script = _sample_script("threat-004")
    next_result = GenerationResult(script=next_script, slide_paths=[], video_path=tmp_path / "threat-004.mp4")

    with patch("check_review.check_reaction", return_value="rejected"), \
            patch("check_review.generate_video", return_value=next_result), \
            patch("check_review.request_review", side_effect=requests.exceptions.RequestException("boom")):
        process_review(tmp_path)

    captured = capsys.readouterr()
    assert "Discord 검수 요청 전송에 실패했습니다" in captured.out


def test_process_review_approved_uploads_to_youtube(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    status_path = tmp_path / "review_status.json"
    video_path = tmp_path / "threat-003.mp4"
    video_path.write_bytes(b"fake-mp4")
    thumbnail_path = tmp_path / "threat-003_slide_01.png"
    thumbnail_path.write_bytes(b"fake-png")

    save_review_status(
        status_path,
        ReviewStatus(
            source_id="threat-003", message_id="m", channel_id="c", status="pending", retry_count=0,
            title="제목", description="설명", tags=["a"], video_path=str(video_path),
        ),
    )

    with patch("check_review.check_reaction", return_value="approved"), \
            patch("check_review.build_youtube_client", return_value="youtube-client"), \
            patch("check_review.upload_video", return_value="abc123") as mock_upload, \
            patch("check_review.set_thumbnail") as mock_thumbnail:
        process_review(tmp_path)

    captured = capsys.readouterr()
    assert "https://youtu.be/abc123" in captured.out

    new_status = load_review_status(status_path)
    assert new_status.status == "uploaded"
    assert new_status.youtube_video_id == "abc123"
    assert new_status.published_at is not None
    mock_upload.assert_called_once()
    mock_thumbnail.assert_called_once_with("youtube-client", "abc123", thumbnail_path)


def test_process_review_approved_missing_youtube_credentials(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    status_path = tmp_path / "review_status.json"
    save_review_status(
        status_path,
        ReviewStatus(source_id="threat-003", message_id="m", channel_id="c", status="pending", retry_count=0),
    )

    with patch("check_review.check_reaction", return_value="approved"), \
            patch("check_review.build_youtube_client", side_effect=YouTubeCredentialsError("자격 증명 없음")):
        process_review(tmp_path)

    captured = capsys.readouterr()
    assert "자격 증명 없음" in captured.out

    new_status = load_review_status(status_path)
    assert new_status.status == "approved"


def test_process_review_approved_upload_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    status_path = tmp_path / "review_status.json"
    video_path = tmp_path / "threat-003.mp4"
    video_path.write_bytes(b"fake-mp4")

    save_review_status(
        status_path,
        ReviewStatus(
            source_id="threat-003", message_id="m", channel_id="c", status="pending", retry_count=0,
            video_path=str(video_path),
        ),
    )

    error = HttpError(resp=MagicMock(status=403), content=b"quota exceeded")

    with patch("check_review.check_reaction", return_value="approved"), \
            patch("check_review.build_youtube_client", return_value="youtube-client"), \
            patch("check_review.upload_video", side_effect=error):
        process_review(tmp_path)

    captured = capsys.readouterr()
    assert "업로드에 실패했습니다" in captured.out

    new_status = load_review_status(status_path)
    assert new_status.status == "upload_failed"
    assert new_status.error_message is not None


def test_process_review_approved_without_thumbnail_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    status_path = tmp_path / "review_status.json"
    video_path = tmp_path / "threat-003.mp4"
    video_path.write_bytes(b"fake-mp4")
    # 슬라이드 PNG 파일은 만들지 않음

    save_review_status(
        status_path,
        ReviewStatus(
            source_id="threat-003", message_id="m", channel_id="c", status="pending", retry_count=0,
            video_path=str(video_path),
        ),
    )

    with patch("check_review.check_reaction", return_value="approved"), \
            patch("check_review.build_youtube_client", return_value="youtube-client"), \
            patch("check_review.upload_video", return_value="abc123"), \
            patch("check_review.set_thumbnail") as mock_thumbnail:
        process_review(tmp_path)

    new_status = load_review_status(status_path)
    assert new_status.status == "uploaded"
    mock_thumbnail.assert_not_called()


def test_process_review_approved_uploads_to_youtube_logs_event(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    status_path = tmp_path / "review_status.json"
    video_path = tmp_path / "threat-003.mp4"
    video_path.write_bytes(b"fake-mp4")

    save_review_status(
        status_path,
        ReviewStatus(
            source_id="threat-003", message_id="m", channel_id="c", status="pending", retry_count=0,
            video_path=str(video_path),
        ),
    )

    with patch("check_review.check_reaction", return_value="approved"), \
            patch("check_review.build_youtube_client", return_value="youtube-client"), \
            patch("check_review.upload_video", return_value="abc123"), \
            patch("check_review.set_thumbnail"):
        process_review(tmp_path)

    entries = load_log_entries(tmp_path / "run_log.jsonl")
    assert entries[-1].source_id == "threat-003"
    assert entries[-1].status == "uploaded"
    assert entries[-1].youtube_video_id == "abc123"


def test_process_review_approved_upload_failure_logs_and_alerts(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    status_path = tmp_path / "review_status.json"
    video_path = tmp_path / "threat-003.mp4"
    video_path.write_bytes(b"fake-mp4")

    save_review_status(
        status_path,
        ReviewStatus(
            source_id="threat-003", message_id="m", channel_id="c", status="pending", retry_count=0,
            video_path=str(video_path),
        ),
    )

    error = HttpError(resp=MagicMock(status=403), content=b"quota exceeded")

    with patch("check_review.check_reaction", return_value="approved"), \
            patch("check_review.build_youtube_client", return_value="youtube-client"), \
            patch("check_review.upload_video", side_effect=error), \
            patch("check_review.send_alert") as mock_alert:
        process_review(tmp_path)

    entries = load_log_entries(tmp_path / "run_log.jsonl")
    assert entries[-1].source_id == "threat-003"
    assert entries[-1].status == "upload_failed"
    assert entries[-1].error_message is not None
    mock_alert.assert_called_once()
    assert "threat-003" in mock_alert.call_args[0][0]


def test_process_review_approved_missing_credentials_logs_skip(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    status_path = tmp_path / "review_status.json"
    save_review_status(
        status_path,
        ReviewStatus(source_id="threat-003", message_id="m", channel_id="c", status="pending", retry_count=0),
    )

    with patch("check_review.check_reaction", return_value="approved"), \
            patch("check_review.build_youtube_client", side_effect=YouTubeCredentialsError("자격 증명 없음")):
        process_review(tmp_path)

    entries = load_log_entries(tmp_path / "run_log.jsonl")
    assert entries[-1].source_id == "threat-003"
    assert entries[-1].status == "upload_skipped"


def test_process_review_rejected_after_retry_marks_final_logs_event(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    status_path = tmp_path / "review_status.json"
    save_review_status(
        status_path,
        ReviewStatus(source_id="threat-004", message_id="m2", channel_id="c2", status="pending", retry_count=1),
    )

    with patch("check_review.check_reaction", return_value="rejected"):
        process_review(tmp_path)

    entries = load_log_entries(tmp_path / "run_log.jsonl")
    assert entries[-1].source_id == "threat-004"
    assert entries[-1].status == "rejected_final"


def test_process_review_rejected_no_more_candidates_logs_and_alerts(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    status_path = tmp_path / "review_status.json"
    save_review_status(
        status_path,
        ReviewStatus(source_id="threat-003", message_id="m", channel_id="c", status="pending", retry_count=0),
    )

    with patch("check_review.check_reaction", return_value="rejected"), \
            patch("check_review.generate_video", return_value=None), \
            patch("check_review.send_alert") as mock_alert:
        process_review(tmp_path)

    entries = load_log_entries(tmp_path / "run_log.jsonl")
    assert entries[-1].source_id == "threat-003"
    assert entries[-1].status == "no_candidate"
    mock_alert.assert_called_once()


def test_process_review_rejected_generation_failure_logs_and_alerts(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    status_path = tmp_path / "review_status.json"
    save_review_status(
        status_path,
        ReviewStatus(source_id="threat-003", message_id="m", channel_id="c", status="pending", retry_count=0),
    )

    error = FFmpegNotFoundError("ffmpeg 없음")

    with patch("check_review.check_reaction", return_value="rejected"), \
            patch("check_review.generate_video", side_effect=error), \
            patch("check_review.send_alert") as mock_alert:
        process_review(tmp_path)

    entries = load_log_entries(tmp_path / "run_log.jsonl")
    assert entries[-1].source_id == "threat-003"
    assert entries[-1].status == "generation_failed"
    assert entries[-1].error_message == "ffmpeg 없음"
    mock_alert.assert_called_once()


def test_process_review_rejected_retries_with_next_candidate_logs_generated(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    status_path = tmp_path / "review_status.json"
    save_review_status(
        status_path,
        ReviewStatus(source_id="threat-003", message_id="m", channel_id="c", status="pending", retry_count=0),
    )

    next_script = _sample_script("threat-004")
    next_result = GenerationResult(script=next_script, slide_paths=[], video_path=tmp_path / "threat-004.mp4")

    with patch("check_review.check_reaction", return_value="rejected"), \
            patch("check_review.generate_video", return_value=next_result), \
            patch(
                "check_review.request_review",
                return_value=ReviewStatus(
                    source_id="threat-004", message_id="m2", channel_id="c2", status="pending", retry_count=0,
                    video_path=str(tmp_path / "threat-004.mp4"),
                ),
            ):
        process_review(tmp_path)

    entries = load_log_entries(tmp_path / "run_log.jsonl")
    assert entries[-1].source_id == "threat-004"
    assert entries[-1].status == "generated"
    assert entries[-1].video_path == str(tmp_path / "threat-004.mp4")
