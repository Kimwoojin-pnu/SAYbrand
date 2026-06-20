# 로깅·알림 모듈 (TRD §2.7) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 파이프라인의 매 실행 결과(생성/검수/업로드 성공·실패)를 `output/run_log.jsonl`에 누적 기록하고, 실패(소재 없음/생성 실패/업로드 실패) 시 별도 Discord 웹훅으로 알림을 보내며, `health_check.py`로 "오늘 업로드 성공 여부"를 점검할 수 있게 한다.

**Architecture:** `cardnews/run_log.py`가 `LogEntry` 데이터클래스와 JSONL append/load 함수를 제공하고(향후 `card_news_publish`/실행이력 DB 테이블로 교체 가능한 "나중에 교체" 패턴), `cardnews/alerts.py`가 `DISCORD_ALERT_WEBHOOK_URL` 환경변수 기반 `send_alert()`를 제공한다(미설정 시 안내 후 스킵하는 기존 ffmpeg/Discord/YouTube 패턴과 동일). `run.py`와 `check_review.py`는 각 분기(생성 성공/실패, 소재 없음, 업로드 성공/실패, 반려 등)에서 `log_event()`를 호출해 이력을 남기고, 실패 케이스에서는 `send_alert()`도 호출한다. `health_check.py`는 `run_log.jsonl`을 읽어 오늘 날짜에 `status="uploaded"` 항목이 있는지 확인하고 없으면 알림을 보낸다.

**Tech Stack:** Python 3.13, `dataclasses`, `json`, `pathlib`, `requests`, `datetime` (UTC ISO timestamps), pytest + `unittest.mock`.

---

## File Structure

- Create: `cardnews/run_log.py` — `LogEntry` dataclass, `append_log_entry()`, `load_log_entries()`, `log_event()`
- Create: `cardnews/alerts.py` — `send_alert()`
- Create: `tests/test_run_log.py`
- Create: `tests/test_alerts.py`
- Modify: `.env.example` — add `DISCORD_ALERT_WEBHOOK_URL`
- Modify: `run.py` — log generation outcomes + send alerts on failure
- Create: `tests/test_run.py`
- Modify: `check_review.py` — log review/upload outcomes + send alerts on failure
- Modify: `tests/test_check_review.py` — add coverage for new logging/alert calls
- Create: `health_check.py`
- Create: `tests/test_health_check.py`
- Modify: `README.md` — document `DISCORD_ALERT_WEBHOOK_URL`, `output/run_log.jsonl`, `health_check.py`

---

## Task 1: 실행 이력 로그 모듈 (`cardnews/run_log.py`)

**Files:**
- Create: `cardnews/run_log.py`
- Test: `tests/test_run_log.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_run_log.py`:

```python
import json

from cardnews.run_log import LogEntry, append_log_entry, load_log_entries, log_event


def test_append_log_entry_writes_jsonl_line(tmp_path):
    path = tmp_path / "run_log.jsonl"
    entry = LogEntry(timestamp="2026-06-12T00:00:00+00:00", source_id="threat-003", status="generated")

    append_log_entry(path, entry)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "timestamp": "2026-06-12T00:00:00+00:00",
        "source_id": "threat-003",
        "status": "generated",
        "video_path": "",
        "youtube_video_id": None,
        "error_message": None,
    }


def test_append_log_entry_appends_multiple_lines(tmp_path):
    path = tmp_path / "run_log.jsonl"
    append_log_entry(path, LogEntry(timestamp="t1", source_id="a", status="generated"))
    append_log_entry(path, LogEntry(timestamp="t2", source_id="b", status="uploaded"))

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["source_id"] == "b"


def test_load_log_entries_returns_empty_list_when_file_missing(tmp_path):
    assert load_log_entries(tmp_path / "missing.jsonl") == []


def test_load_log_entries_parses_existing_entries(tmp_path):
    path = tmp_path / "run_log.jsonl"
    append_log_entry(path, LogEntry(timestamp="t1", source_id="a", status="generated"))
    append_log_entry(path, LogEntry(timestamp="t2", source_id="b", status="uploaded", youtube_video_id="abc123"))

    entries = load_log_entries(path)

    assert entries == [
        LogEntry(timestamp="t1", source_id="a", status="generated"),
        LogEntry(timestamp="t2", source_id="b", status="uploaded", youtube_video_id="abc123"),
    ]


def test_log_event_writes_entry_with_current_timestamp(tmp_path):
    log_event(tmp_path, source_id="threat-003", status="generated", video_path="output/threat-003.mp4")

    entries = load_log_entries(tmp_path / "run_log.jsonl")
    assert len(entries) == 1
    assert entries[0].source_id == "threat-003"
    assert entries[0].status == "generated"
    assert entries[0].video_path == "output/threat-003.mp4"
    assert entries[0].timestamp
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_run_log.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cardnews.run_log'`

- [ ] **Step 3: Write the implementation**

Create `cardnews/run_log.py`:

```python
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class LogEntry:
    timestamp: str
    source_id: str | None
    status: str
    video_path: str = ""
    youtube_video_id: str | None = None
    error_message: str | None = None


def append_log_entry(path: Path, entry: LogEntry) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")


def load_log_entries(path: Path) -> list[LogEntry]:
    if not path.exists():
        return []

    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        entries.append(LogEntry(**json.loads(line)))
    return entries


def log_event(
    output_dir: Path,
    source_id: str | None,
    status: str,
    video_path: str = "",
    youtube_video_id: str | None = None,
    error_message: str | None = None,
) -> None:
    entry = LogEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        source_id=source_id,
        status=status,
        video_path=video_path,
        youtube_video_id=youtube_video_id,
        error_message=error_message,
    )
    append_log_entry(output_dir / "run_log.jsonl", entry)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_run_log.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add cardnews/run_log.py tests/test_run_log.py
git commit -m "feat: add JSONL execution history log module"
```

---

## Task 2: 실패 알림 모듈 (`cardnews/alerts.py`)

**Files:**
- Create: `cardnews/alerts.py`
- Test: `tests/test_alerts.py`
- Modify: `.env.example`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_alerts.py`:

```python
from unittest.mock import patch

import requests

from cardnews.alerts import send_alert


def test_send_alert_skips_when_webhook_not_configured(monkeypatch, capsys):
    monkeypatch.delenv("DISCORD_ALERT_WEBHOOK_URL", raising=False)

    with patch("cardnews.alerts.requests.post") as mock_post:
        send_alert("테스트 알림")

    mock_post.assert_not_called()
    captured = capsys.readouterr()
    assert "DISCORD_ALERT_WEBHOOK_URL이 설정되지 않아" in captured.out


def test_send_alert_posts_message_to_webhook(monkeypatch):
    monkeypatch.setenv("DISCORD_ALERT_WEBHOOK_URL", "https://discord.com/api/webhooks/alert")

    with patch("cardnews.alerts.requests.post") as mock_post:
        send_alert("업로드 실패")

    mock_post.assert_called_once_with(
        "https://discord.com/api/webhooks/alert",
        json={"content": "업로드 실패"},
        timeout=10,
    )


def test_send_alert_handles_request_exception(monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_ALERT_WEBHOOK_URL", "https://discord.com/api/webhooks/alert")

    with patch("cardnews.alerts.requests.post", side_effect=requests.exceptions.RequestException("boom")):
        send_alert("업로드 실패")

    captured = capsys.readouterr()
    assert "실패 알림 전송 중 오류가 발생했습니다" in captured.out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_alerts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cardnews.alerts'`

- [ ] **Step 3: Write the implementation**

Create `cardnews/alerts.py`:

```python
import os

import requests


def send_alert(message: str) -> None:
    webhook_url = os.environ.get("DISCORD_ALERT_WEBHOOK_URL")
    if not webhook_url:
        print("DISCORD_ALERT_WEBHOOK_URL이 설정되지 않아 알림을 보내지 않았습니다.")
        return

    try:
        requests.post(webhook_url, json={"content": message}, timeout=10)
    except requests.exceptions.RequestException as error:
        print(f"실패 알림 전송 중 오류가 발생했습니다: {error}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_alerts.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Add `DISCORD_ALERT_WEBHOOK_URL` to `.env.example`**

Read current `.env.example` (4 existing entries: `DISCORD_WEBHOOK_URL`, `DISCORD_BOT_TOKEN`, `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`). Append at the end:

```
# 실패 알림용 Discord Incoming Webhook URL (검수용 웹훅과는 별도 채널 권장)
DISCORD_ALERT_WEBHOOK_URL=
```

- [ ] **Step 6: Commit**

```bash
git add cardnews/alerts.py tests/test_alerts.py .env.example
git commit -m "feat: add Discord failure alert module"
```

---

## Task 3: `run.py`에 실행 이력 로깅 + 실패 알림 연결

**Files:**
- Modify: `run.py`
- Create: `tests/test_run.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_run.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_run.py -v`
Expected: FAIL — `AttributeError` / `ImportError`, since `run.log_event` and `run.send_alert` don't exist yet.

- [ ] **Step 3: Update `run.py`**

Replace the full contents of `run.py`:

```python
import sys
from pathlib import Path

import requests

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_run.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full test suite**

Run: `pytest -q`
Expected: All previously-passing tests still pass (no regressions).

- [ ] **Step 6: Commit**

```bash
git add run.py tests/test_run.py
git commit -m "feat: log generation outcomes and alert on run.py failures"
```

---

## Task 4: `check_review.py`의 YouTube 업로드 결과 로깅 + 업로드 실패 알림

**Files:**
- Modify: `check_review.py` (`_upload_to_youtube`, imports)
- Modify: `tests/test_check_review.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_check_review.py` (after the existing YouTube-related tests, e.g. after `test_process_review_approved_without_thumbnail_file`):

```python
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
```

Add the new import at the top of `tests/test_check_review.py`:

```python
from cardnews.run_log import load_log_entries
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_check_review.py -v -k "logs_event or logs_and_alerts or logs_skip"`
Expected: FAIL — `run_log.jsonl` not created / `check_review.send_alert` doesn't exist.

- [ ] **Step 3: Update `check_review.py` imports and `_upload_to_youtube`**

Add these imports near the top of `check_review.py` (alongside the existing `cardnews` imports):

```python
from cardnews.alerts import send_alert
from cardnews.run_log import log_event
```

Replace the `_upload_to_youtube` function body:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_check_review.py -v`
Expected: PASS — all tests including the 3 new ones.

- [ ] **Step 5: Run the full test suite**

Run: `pytest -q`
Expected: All tests pass (no regressions).

- [ ] **Step 6: Commit**

```bash
git add check_review.py tests/test_check_review.py
git commit -m "feat: log YouTube upload outcomes and alert on upload failure"
```

---

## Task 5: `check_review.py`의 반려/소재없음/재생성 결과 로깅 + 알림

**Files:**
- Modify: `check_review.py` (`process_review`)
- Modify: `tests/test_check_review.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_check_review.py`:

```python
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
```

Add `FFmpegNotFoundError` to the imports at the top of `tests/test_check_review.py`:

```python
from cardnews.video import FFmpegNotFoundError
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_check_review.py -v -k "rejected_after_retry_marks_final_logs_event or no_more_candidates_logs_and_alerts or generation_failure_logs_and_alerts or retries_with_next_candidate_logs_generated"`
Expected: FAIL — no `run_log.jsonl` entries written yet for these branches.

- [ ] **Step 3: Update `process_review` in `check_review.py`**

Replace the body of `process_review` from the `# reaction == "rejected"` comment to the end of the function:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_check_review.py -v`
Expected: PASS — all tests including the 4 new ones.

- [ ] **Step 5: Run the full test suite**

Run: `pytest -q`
Expected: All tests pass (no regressions).

- [ ] **Step 6: Commit**

```bash
git add check_review.py tests/test_check_review.py
git commit -m "feat: log review outcomes and alert on regeneration failures"
```

---

## Task 6: 일일 헬스체크 스크립트 (`health_check.py`)

**Files:**
- Create: `health_check.py`
- Create: `tests/test_health_check.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_health_check.py`:

```python
from unittest.mock import patch

from cardnews.run_log import LogEntry, append_log_entry, log_event
from health_check import has_uploaded_today, main


def test_has_uploaded_today_true_when_uploaded_entry_exists_for_today(tmp_path):
    log_event(tmp_path, source_id="threat-003", status="uploaded", youtube_video_id="abc123")

    assert has_uploaded_today(tmp_path) is True


def test_has_uploaded_today_false_when_no_entries(tmp_path):
    assert has_uploaded_today(tmp_path) is False


def test_has_uploaded_today_false_when_only_old_entries(tmp_path):
    append_log_entry(
        tmp_path / "run_log.jsonl",
        LogEntry(timestamp="2000-01-01T00:00:00+00:00", source_id="threat-001", status="uploaded"),
    )

    assert has_uploaded_today(tmp_path) is False


def test_main_sends_alert_when_no_upload_today(capsys):
    with patch("health_check.has_uploaded_today", return_value=False), \
            patch("health_check.send_alert") as mock_alert:
        main()

    mock_alert.assert_called_once()
    captured = capsys.readouterr()
    assert "오늘 업로드된 카드뉴스가 없습니다" in captured.out


def test_main_skips_alert_when_upload_today(capsys):
    with patch("health_check.has_uploaded_today", return_value=True), \
            patch("health_check.send_alert") as mock_alert:
        main()

    mock_alert.assert_not_called()
    captured = capsys.readouterr()
    assert "정상적으로 업로드되었습니다" in captured.out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_health_check.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'health_check'`

- [ ] **Step 3: Write the implementation**

Create `health_check.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_health_check.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Run the full test suite**

Run: `pytest -q`
Expected: All tests pass (no regressions).

- [ ] **Step 6: Commit**

```bash
git add health_check.py tests/test_health_check.py
git commit -m "feat: add daily upload health check script"
```

---

## Task 7: README 문서화

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add alert webhook setup section**

In `README.md`, after the existing "## YouTube 업로드 설정" section (which ends with "설정하지 않으면 검수 승인 후 업로드 단계에서 안내 메시지와 함께 건너뜁니다."), insert a new section:

```markdown

## 실패 알림 및 실행 이력

모든 실행 결과(생성 성공/실패, 소재 없음, 검수 반려, 업로드 성공/실패)는 `output/run_log.jsonl`에 한 줄씩 누적 기록됩니다.

실패(소재 없음/생성 실패/업로드 실패) 시 별도 Discord 웹훅으로 알림을 보내려면 검수용 채널과 다른 채널의 Incoming Webhook URL을 환경변수로 설정합니다 (PowerShell 예시):

```powershell
$env:DISCORD_ALERT_WEBHOOK_URL = "https://discord.com/api/webhooks/..."
```

설정하지 않으면 알림 전송을 건너뛰고 안내 메시지만 출력합니다.

## 일일 헬스체크

매일 한 번 다음 명령으로 "오늘 카드뉴스가 정상적으로 업로드되었는지"를 점검할 수 있습니다:

```bash
python health_check.py
```

`output/run_log.jsonl`에 오늘 날짜의 `status: "uploaded"` 항목이 없으면 `DISCORD_ALERT_WEBHOOK_URL`로 알림을 보냅니다. Windows 작업 스케줄러나 Cron 등으로 하루 끝에 한 번 실행하는 것을 권장합니다.
```

- [ ] **Step 2: Update the "사용법" section**

In the existing "## 사용법" section, after step 3's bullet list (반려 2차 항목 다음), add a 4th step:

```markdown
4. (선택, 1일 1회) 오늘 업로드 성공 여부 점검:
   ```bash
   python health_check.py
   ```
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document failure alerts, run log, and health check"
```

---

## Self-Review Notes

- **TRD §2.7 저장 (실행 이력)**: covered by Task 1 (`run_log.jsonl`) + Tasks 3–5 (log calls at every terminal state: `generated`, `generation_failed`, `no_candidate`, `uploaded`, `upload_failed`, `upload_skipped`, `rejected_final`). "영상 URL"은 `youtube_video_id`로부터 `https://youtu.be/<id>`로 구성 가능하므로 별도 필드를 추가하지 않음.
- **TRD §2.7 알림 (실패 시)**: covered by Task 2 (`send_alert`) + Tasks 3, 5 for 소재 없음/생성 실패, Task 4 for 업로드 실패.
- **TRD §2.7 모니터링 (헬스체크)**: covered by Task 6 (`health_check.py`).
- **TRD §7 "단계별 실행 로그 적재 + 실패 시 알림"**: every failure branch in `run.py`/`check_review.py` now logs and (where applicable) alerts.
- **TRD §7 "각 단계는 독립 재시도 가능"**: unchanged — existing retry logic in `check_review.py` (재시도 1회) is preserved; logging is additive and does not change control flow.
- All new external calls (`send_alert`'s `requests.post`) follow the existing "swap later" / "configured? send : skip" pattern used for ffmpeg/Discord/YouTube.
