import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from cardnews.video import (
    FFmpegNotFoundError,
    assemble_video,
    ensure_ffmpeg_available,
)


def test_ensure_ffmpeg_available_raises_when_missing():
    with patch("cardnews.video.shutil.which", return_value=None):
        with pytest.raises(FFmpegNotFoundError):
            ensure_ffmpeg_available()


def test_ensure_ffmpeg_available_passes_when_present():
    with patch("cardnews.video.shutil.which", return_value="/usr/bin/ffmpeg"):
        ensure_ffmpeg_available()


def test_assemble_video_raises_for_empty_slide_paths(tmp_path):
    with pytest.raises(ValueError):
        assemble_video([], tmp_path / "output.mp4")


def test_assemble_video_without_bgm_runs_ffmpeg_per_slide_and_concatenates(tmp_path):
    slide_paths = [
        tmp_path / "threat-003_slide_01.png",
        tmp_path / "threat-003_slide_02.png",
        tmp_path / "threat-003_slide_03.png",
    ]
    for path in slide_paths:
        path.write_bytes(b"fake-png")

    output_path = tmp_path / "threat-003.mp4"

    with patch("cardnews.video.shutil.which", return_value="/usr/bin/ffmpeg"), \
            patch("cardnews.video.subprocess.run") as mock_run, \
            patch("cardnews.video.shutil.copyfile") as mock_copy:
        result = assemble_video(slide_paths, output_path)

    assert result == output_path
    # 슬라이드 3개 -> 클립 생성 3회 + concat 1회 = 4회
    assert mock_run.call_count == 4
    for call in mock_run.call_args_list:
        assert call.args[0][0] == "ffmpeg"
        assert call.kwargs["check"] is True
    mock_copy.assert_called_once()


def test_assemble_video_with_bgm_mixes_audio(tmp_path):
    slide_paths = [
        tmp_path / "threat-003_slide_01.png",
        tmp_path / "threat-003_slide_02.png",
    ]
    for path in slide_paths:
        path.write_bytes(b"fake-png")

    bgm_path = tmp_path / "bgm.mp3"
    bgm_path.write_bytes(b"fake-mp3")

    output_path = tmp_path / "threat-003.mp4"

    with patch("cardnews.video.shutil.which", return_value="/usr/bin/ffmpeg"), \
            patch("cardnews.video.subprocess.run") as mock_run:
        result = assemble_video(slide_paths, output_path, bgm_path=bgm_path)

    assert result == output_path
    # 슬라이드 2개 -> 클립 생성 2회 + concat 1회 + bgm 믹싱 1회 = 4회
    assert mock_run.call_count == 4
    last_call_args = mock_run.call_args_list[-1].args[0]
    assert "-stream_loop" in last_call_args
    assert str(bgm_path) in last_call_args


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_assemble_video_integration_creates_real_mp4(tmp_path):
    from cardnews.mock_data import load_sample_threats
    from cardnews.renderer import render_slides
    from cardnews.scripter import generate_script

    record = load_sample_threats()[0]
    script = generate_script(record)
    slide_paths = render_slides(script, tmp_path / "slides")

    output_path = tmp_path / "output.mp4"
    result = assemble_video(slide_paths, output_path)

    assert result.exists()
    assert result.stat().st_size > 0
