import sys
from datetime import datetime, timezone
from pathlib import Path

from cardnews.alerts import send_alert
from cardnews.run_log import load_log_entries


def has_uploaded_today(output_dir: Path) -> bool:
    today = datetime.now(timezone.utc).date().isoformat()
    entries = load_log_entries(output_dir / "run_log.jsonl")
    return any(entry.status == "uploaded" and entry.timestamp.startswith(today) for entry in entries)


def main() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    output_dir = Path(__file__).parent / "output"

    if has_uploaded_today(output_dir):
        print("오늘 카드뉴스가 정상적으로 업로드되었습니다.")
        return

    print("오늘 업로드된 카드뉴스가 없습니다.")
    send_alert("[카드뉴스 파이프라인] 오늘 업로드된 카드뉴스가 없습니다. 파이프라인 상태를 확인해주세요.")


if __name__ == "__main__":
    main()
