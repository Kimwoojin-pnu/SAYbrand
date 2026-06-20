"""FR-9: 운영 이력 조회 CLI.

사용법:
    python history.py           # 최근 20건
    python history.py --all     # 전체 이력
    python history.py --status uploaded  # 특정 상태만
"""
import argparse
import sys
from pathlib import Path

from cardnews.run_log import load_log_entries
from cardnews.review_status import load_review_status

_DEFAULT_OUTPUT_DIR = Path(__file__).parent / "output"


def _truncate(text: str | None, width: int) -> str:
    if not text:
        return "-"
    return text[:width - 1] + "…" if len(text) > width else text


def print_run_log(entries, limit: int | None, status_filter: str | None) -> None:
    if status_filter:
        entries = [e for e in entries if e.status == status_filter]
    if limit:
        entries = entries[-limit:]

    if not entries:
        print("표시할 실행 이력이 없습니다.")
        return

    header = f"{'날짜/시각':<28} {'소재 ID':<18} {'상태':<22} {'YouTube ID':<14} 에러"
    print(header)
    print("-" * 100)
    for e in reversed(entries):
        ts = _truncate(e.timestamp, 27)
        sid = _truncate(e.source_id, 17)
        yt = _truncate(e.youtube_video_id, 13)
        err = _truncate(e.error_message, 35)
        print(f"{ts:<28} {sid:<18} {e.status:<22} {yt:<14} {err}")

    print(f"\n총 {len(entries)}건")


def print_current_review(output_dir: Path) -> None:
    status = load_review_status(output_dir / "review_status.json")
    if status is None:
        print("\n[현재 검수 상태] 없음")
        return

    print("\n[현재 검수 상태]")
    print(f"  소재 ID : {status.source_id}")
    print(f"  상태    : {status.status}")
    print(f"  제목    : {status.title or '-'}")
    if status.youtube_video_id:
        print(f"  YouTube : https://youtu.be/{status.youtube_video_id}")
    if status.error_message:
        print(f"  에러    : {status.error_message}")


def main(output_dir: Path | None = None) -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="카드뉴스 파이프라인 운영 이력 조회")
    parser.add_argument("--all", action="store_true", help="전체 이력 표시 (기본 최근 20건)")
    parser.add_argument("--status", metavar="STATUS", help="특정 상태만 필터링 (예: uploaded, generation_failed)")
    parser.add_argument("--no-review", action="store_true", help="현재 검수 상태 표시 생략")
    args = parser.parse_args()

    out = output_dir or _DEFAULT_OUTPUT_DIR
    limit = None if args.all else 20
    entries = load_log_entries(out / "run_log.jsonl")
    print_run_log(entries, limit=limit, status_filter=args.status)

    if not args.no_review:
        print_current_review(out)


if __name__ == "__main__":
    main()
