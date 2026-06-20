import os
from dataclasses import dataclass
from pathlib import Path

from cardnews.discord_review import send_preview
from cardnews.models import CardNewsScript
from cardnews.pipeline import run_pipeline
from cardnews.review_status import ReviewStatus, save_review_status
from cardnews.video import assemble_video

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BGM_DIR = PROJECT_ROOT / "assets" / "bgm"


@dataclass
class GenerationResult:
    script: CardNewsScript
    slide_paths: list[Path]
    video_path: Path


def _find_bgm(bgm_dir: Path) -> Path | None:
    if not bgm_dir.is_dir():
        return None

    matches = sorted(bgm_dir.glob("*.mp3"))
    return matches[0] if matches else None


def generate_video(
    output_dir: Path,
    used_ids: set[str] | None = None,
) -> GenerationResult | None:
    script = run_pipeline(output_dir, used_ids=used_ids)
    if script is None:
        return None

    # Safe to glob even on re-runs: render_slides() overwrites same-named slide files for this source_id.
    slide_paths = sorted(output_dir.glob(f"{script.source_id}_slide_*.png"))
    bgm_path = _find_bgm(BGM_DIR)
    video_path = assemble_video(
        slide_paths,
        output_dir / f"{script.source_id}.mp4",
        bgm_path=bgm_path,
    )

    return GenerationResult(script=script, slide_paths=slide_paths, video_path=video_path)


def request_review(result: GenerationResult, output_dir: Path) -> ReviewStatus | None:
    webhook_url = (
        os.environ.get("DISCORD_WEBHOOK_URL")
        or os.environ.get("DISCORD_ALERT_WEBHOOK_URL")
    )
    if not webhook_url:
        return None

    message_info = send_preview(result.script, result.video_path, result.slide_paths, webhook_url)

    status = ReviewStatus(
        source_id=result.script.source_id,
        message_id=message_info["id"],
        channel_id=message_info["channel_id"],
        status="pending",
        retry_count=0,
        title=result.script.title,
        description=result.script.description,
        tags=list(result.script.tags),
        video_path=str(result.video_path),
    )
    save_review_status(output_dir / "review_status.json", status)
    return status
