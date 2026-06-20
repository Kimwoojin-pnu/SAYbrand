from pathlib import Path
from unittest.mock import patch

from cardnews.models import CardNewsScript, Slide
from cardnews.orchestrator import GenerationResult
from cardnews.video import FFmpegNotFoundError
from run import main


def _sample_result(source_id: str = "threat-003") -> GenerationResult:
    script = CardNewsScript(
        source_id=source_id,
        title="제목",
        slides=[Slide(headline="h", body="b")],
        description="설명",
        tags=["태그"],
    )
    return GenerationResult(script=script, slide_paths=[], video_path=Path("output") / f"{source_id}.mp4")


def test_main_logs_generation_failure_and_sends_alert():
    error = FFmpegNotFoundError("ffmpeg 없음")

    with patch("run.generate_video", side_effect=error), \
            patch("run.log_event") as mock_log, \
            patch("run.send_alert") as mock_alert:
        main()

    _, kwargs = mock_log.call_args
    assert kwargs["status"] == "generation_failed"
    assert kwargs["error_message"] == "ffmpeg 없음"
    mock_alert.assert_called_once()
    assert "영상 생성에 실패했습니다" in mock_alert.call_args[0][0]


def test_main_logs_no_candidate_and_sends_alert():
    with patch("run.generate_video", return_value=None), \
            patch("run.log_event") as mock_log, \
            patch("run.send_alert") as mock_alert:
        main()

    _, kwargs = mock_log.call_args
    assert kwargs["status"] == "no_candidate"
    mock_alert.assert_called_once()
    assert "소재가 없습니다" in mock_alert.call_args[0][0]


def test_main_logs_generated_on_success():
    result = _sample_result()

    with patch("run.generate_video", return_value=result), \
            patch("run.request_review", return_value=None), \
            patch("run.log_event") as mock_log, \
            patch("run.send_alert") as mock_alert:
        main()

    _, kwargs = mock_log.call_args
    assert kwargs["status"] == "generated"
    assert kwargs["source_id"] == "threat-003"
    assert kwargs["video_path"] == str(result.video_path)
    mock_alert.assert_not_called()
