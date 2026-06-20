import shutil
import subprocess
import tempfile
from pathlib import Path

SLIDE_WIDTH = 1080
SLIDE_HEIGHT = 1920
SECONDS_PER_SLIDE = 5.0
MAX_DURATION_SECONDS = 60.0
FRAME_RATE = 30
BGM_VOLUME = 0.3


class FFmpegNotFoundError(RuntimeError):
    """ffmpeg 실행 파일을 PATH에서 찾을 수 없을 때 발생."""


def ensure_ffmpeg_available() -> None:
    if shutil.which("ffmpeg") is None:
        raise FFmpegNotFoundError(
            "ffmpeg를 찾을 수 없습니다. Windows에서는 'winget install ffmpeg' 명령으로 "
            "설치한 뒤 새 터미널에서 다시 실행해주세요. "
            "(참고: https://ffmpeg.org/download.html)"
        )


def _slide_duration(slide_count: int) -> float:
    return min(SECONDS_PER_SLIDE, MAX_DURATION_SECONDS / slide_count)


def _build_clip(slide_path: Path, clip_path: Path, duration: float) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(slide_path),
            "-t", str(duration),
            "-r", str(FRAME_RATE),
            "-vf", f"scale={SLIDE_WIDTH}:{SLIDE_HEIGHT},format=yuv420p",
            "-c:v", "libx264",
            str(clip_path),
        ],
        check=True,
        capture_output=True,
    )


def _concat_clips(clip_paths: list[Path], list_file: Path, output_path: Path) -> None:
    # Relative filenames only work because list_file and clip_paths share the same temp directory.
    list_file.write_text(
        "\n".join(f"file '{clip.name}'" for clip in clip_paths),
        encoding="utf-8",
    )
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )


def _mix_bgm(video_path: Path, bgm_path: Path, output_path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-stream_loop", "-1",
            "-i", str(bgm_path),
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac",
            "-filter:a", f"volume={BGM_VOLUME}",
            "-shortest",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )


def assemble_video(
    slide_paths: list[Path],
    output_path: Path,
    bgm_path: Path | None = None,
) -> Path:
    if not slide_paths:
        raise ValueError("최소 1개 이상의 슬라이드 이미지가 필요합니다.")
    ensure_ffmpeg_available()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = _slide_duration(len(slide_paths))

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        clip_paths = []
        for index, slide_path in enumerate(slide_paths, start=1):
            clip_path = tmp_path / f"clip_{index:02d}.mp4"
            _build_clip(slide_path, clip_path, duration)
            clip_paths.append(clip_path)

        list_file = tmp_path / "concat_list.txt"
        concatenated_path = tmp_path / "concatenated.mp4"
        _concat_clips(clip_paths, list_file, concatenated_path)

        if bgm_path is not None:
            _mix_bgm(concatenated_path, bgm_path, output_path)
        else:
            shutil.copyfile(concatenated_path, output_path)

    return output_path
