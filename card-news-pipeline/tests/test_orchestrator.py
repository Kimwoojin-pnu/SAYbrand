from pathlib import Path
from unittest.mock import patch

from cardnews.models import CardNewsScript, Slide
from cardnews.orchestrator import GenerationResult, _find_bgm, generate_video, request_review
from cardnews.review_status import load_review_status


def _sample_script() -> CardNewsScript:
    return CardNewsScript(
        source_id="threat-003",
        title="브랜드를 위협하는 순간: 해시태그 확산",
        slides=[Slide(headline="이런 일이 있었습니다", body="본문")],
        description="설명입니다",
        tags=["브랜드리스크", "해시태그확산"],
    )


def test_find_bgm_returns_none_when_no_mp3(tmp_path):
    assert _find_bgm(tmp_path) is None


def test_find_bgm_returns_first_mp3_alphabetically(tmp_path):
    (tmp_path / "b.mp3").write_bytes(b"x")
    (tmp_path / "a.mp3").write_bytes(b"x")

    assert _find_bgm(tmp_path) == tmp_path / "a.mp3"


def test_generate_video_returns_none_when_no_candidate(tmp_path):
    with patch("cardnews.orchestrator.run_pipeline", return_value=None):
        result = generate_video(tmp_path)

    assert result is None


def test_generate_video_returns_script_slides_and_video(tmp_path):
    script = _sample_script()
    slide_path = tmp_path / f"{script.source_id}_slide_01.png"
    slide_path.write_bytes(b"fake-png")
    video_path = tmp_path / f"{script.source_id}.mp4"

    with patch("cardnews.orchestrator.run_pipeline", return_value=script), \
            patch("cardnews.orchestrator.assemble_video", return_value=video_path) as mock_assemble:
        result = generate_video(tmp_path)

    assert result == GenerationResult(script=script, slide_paths=[slide_path], video_path=video_path)
    mock_assemble.assert_called_once()
    args, kwargs = mock_assemble.call_args
    assert args[0] == [slide_path]
    assert args[1] == tmp_path / f"{script.source_id}.mp4"
    assert "bgm_path" in kwargs


def test_request_review_returns_none_without_webhook_env(tmp_path, monkeypatch):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    result = GenerationResult(script=_sample_script(), slide_paths=[], video_path=tmp_path / "v.mp4")

    assert request_review(result, tmp_path) is None


def test_request_review_sends_preview_and_saves_status(tmp_path, monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
    script = _sample_script()
    result = GenerationResult(script=script, slide_paths=[], video_path=tmp_path / "v.mp4")

    with patch(
        "cardnews.orchestrator.send_preview",
        return_value={"id": "msg1", "channel_id": "chan1"},
    ):
        status = request_review(result, tmp_path)

    assert status.source_id == script.source_id
    assert status.message_id == "msg1"
    assert status.channel_id == "chan1"
    assert status.status == "pending"
    assert status.retry_count == 0
    assert status.title == script.title
    assert status.description == script.description
    assert status.tags == script.tags
    assert status.video_path == str(result.video_path)
    assert load_review_status(tmp_path / "review_status.json") == status
