import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from cardnews.alerts import send_alert
from cardnews.orchestrator import generate_video, request_review
from cardnews.run_log import log_event
from cardnews.video import FFmpegNotFoundError


def main() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    output_dir = Path(__file__).parent / "output"

    try:
        result = generate_video(output_dir)
    except FFmpegNotFoundError as error:
        print(error)
        log_event(output_dir, source_id=None, status="generation_failed", error_message=str(error))
        send_alert(f"[카드뉴스 파이프라인] 영상 생성에 실패했습니다: {error}")
        return

    if result is None:
        print("생성할 새 카드뉴스 소재가 없습니다.")
        log_event(output_dir, source_id=None, status="no_candidate")
        send_alert("[카드뉴스 파이프라인] 오늘 생성할 새 카드뉴스 소재가 없습니다.")
        return

    script = result.script
    print("카드뉴스 생성 완료")
    print(f"제목: {script.title}")
    print(f"설명: {script.description}")
    print(f"태그: {', '.join(script.tags)}")
    print(f"슬라이드 {len(script.slides)}장이 다음 위치에 저장되었습니다: {output_dir}")
    print(f"영상이 다음 위치에 저장되었습니다: {result.video_path}")

    log_event(output_dir, source_id=script.source_id, status="generated", video_path=str(result.video_path))

    try:
        review_status = request_review(result, output_dir)
    except requests.exceptions.RequestException as error:
        print(f"Discord 검수 요청 전송에 실패했습니다: {error}")
        return

    if review_status is None:
        print("DISCORD_WEBHOOK_URL이 설정되지 않아 검수 요청을 보내지 않았습니다.")
    else:
        print(f"Discord 검수 요청을 전송했습니다 (메시지 ID: {review_status.message_id})")


if __name__ == "__main__":
    main()
