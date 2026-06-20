import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from googleapiclient.errors import HttpError

from cardnews.alerts import send_alert
from cardnews.discord_review import check_reaction
from cardnews.orchestrator import generate_video, request_review
from cardnews.review_status import ReviewStatus, load_review_status, save_review_status
from cardnews.run_log import log_event
from cardnews.video import FFmpegNotFoundError
from cardnews.youtube_upload import YouTubeCredentialsError, build_youtube_client, set_thumbnail, upload_video


def process_review(output_dir: Path) -> None:
    status_path = output_dir / "review_status.json"
    status = load_review_status(status_path)

    if status is None:
        print("검수 대기 중인 카드뉴스가 없습니다.")
        return

    if status.status != "pending":
        print(f"이미 처리된 검수입니다 (상태: {status.status})")
        return

    bot_token = os.environ.get("DISCORD_BOT_TOKEN")
    if not bot_token:
        print("DISCORD_BOT_TOKEN이 설정되지 않았습니다.")
        return

    try:
        reaction = check_reaction(status.channel_id, status.message_id, bot_token)
    except requests.exceptions.RequestException as error:
        print(f"Discord 반응 조회에 실패했습니다: {error}")
        return

    if reaction == "pending":
        print("아직 검수 반응이 없습니다.")
        return

    if reaction == "approved":
        status.status = "approved"
        save_review_status(status_path, status)
        print("승인되었습니다. YouTube 업로드를 진행합니다.")
        _upload_to_youtube(status_path, status)
        return

    # reaction == "rejected"
    if status.retry_count >= 1:
        status.status = "rejected_final"
        save_review_status(status_path, status)
        print("재시도 후에도 반려되어 발행하지 않습니다.")
        log_event(output_dir, source_id=status.source_id, status="rejected_final")
        return

    try:
        next_result = generate_video(output_dir, used_ids={status.source_id})
    except FFmpegNotFoundError as error:
        print(error)
        log_event(output_dir, source_id=status.source_id, status="generation_failed", error_message=str(error))
        send_alert(f"[카드뉴스 파이프라인] 재시도 영상 생성에 실패했습니다: {error}")
        return

    if next_result is None:
        status.status = "rejected_final"
        save_review_status(status_path, status)
        print("반려되었고, 대체할 다음 후보 소재가 없어 발행하지 않습니다.")
        log_event(output_dir, source_id=status.source_id, status="no_candidate")
        send_alert("[카드뉴스 파이프라인] 반려 후 대체할 다음 후보 소재가 없습니다.")
        return

    try:
        new_status = request_review(next_result, output_dir)
    except requests.exceptions.RequestException as error:
        print(f"반려되어 다음 후보로 영상을 재생성했지만, Discord 검수 요청 전송에 실패했습니다: {error}")
        return

    if new_status is None:
        print("반려되어 다음 후보로 영상을 재생성했지만, DISCORD_WEBHOOK_URL이 설정되지 않아 검수 요청을 보내지 못했습니다.")
        return

    new_status.retry_count = status.retry_count + 1
    save_review_status(status_path, new_status)
    print(f"반려되어 다음 후보({new_status.source_id})로 재시도 검수 요청을 보냈습니다.")
    log_event(output_dir, source_id=new_status.source_id, status="generated", video_path=new_status.video_path)


def _upload_to_youtube(status_path: Path, status: ReviewStatus) -> None:
    output_dir = status_path.parent

    try:
        youtube = build_youtube_client()
    except YouTubeCredentialsError as error:
        print(error)
        log_event(output_dir, source_id=status.source_id, status="upload_skipped", error_message=str(error))
        return

    video_path = Path(status.video_path)
    try:
        video_id = upload_video(youtube, status, video_path)
    except HttpError as error:
        status.status = "upload_failed"
        status.error_message = str(error)
        save_review_status(status_path, status)
        print(f"YouTube 업로드에 실패했습니다: {error}")
        log_event(output_dir, source_id=status.source_id, status="upload_failed", error_message=str(error))
        send_alert(f"[카드뉴스 파이프라인] YouTube 업로드에 실패했습니다 (소재: {status.source_id}): {error}")
        return

    thumbnail_path = video_path.parent / f"{status.source_id}_slide_01.png"
    if thumbnail_path.exists():
        try:
            set_thumbnail(youtube, video_id, thumbnail_path)
        except HttpError as error:
            print(f"썸네일 등록에 실패했습니다: {error}")

    status.status = "uploaded"
    status.youtube_video_id = video_id
    status.published_at = datetime.now(timezone.utc).isoformat()
    save_review_status(status_path, status)
    print(f"YouTube에 비공개로 업로드되었습니다: https://youtu.be/{video_id}")
    log_event(
        output_dir,
        source_id=status.source_id,
        status="uploaded",
        video_path=status.video_path,
        youtube_video_id=video_id,
    )


def main() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    output_dir = Path(__file__).parent / "output"
    process_review(output_dir)


if __name__ == "__main__":
    main()
