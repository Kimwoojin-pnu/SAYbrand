# Finalize Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SAYbrand DB 연동, LLM 스크립팅, YouTube 업로드 재시도, Windows 작업 스케줄러를 구현하여 파이프라인을 프로덕션 레디 상태로 완성한다.

**Architecture:** `pipeline.py`가 현재 `mock_data`와 template `scripter`를 직접 임포트하는 구조를 유지하면서, 두 모듈을 환경변수 기반 어댑터(`db_source.py`, `llm_scripter.py`)로 교체한다. 환경변수 미설정 시 기존 mock/템플릿으로 폴백하여 테스트가 API 키·DB 없이도 통과한다.

**Tech Stack:** `psycopg2-binary` (PostgreSQL 연결), `anthropic` SDK (Claude Haiku 스크립팅), `googleapiclient` (기존 YouTube 업로드), PowerShell (Windows 작업 스케줄러)

---

## Task 1: 패키지 추가 및 SAYbrand DB 어댑터

**Files:**
- Modify: `requirements.txt`
- Create: `cardnews/db_source.py`
- Modify: `cardnews/pipeline.py`
- Create: `tests/test_db_source.py`

### 연결 정보 (절대 코드에 하드코딩 금지 — 환경변수로만 사용)
- `DATABASE_URL=postgresql://readonly_user:brand0192@zephyr.proxy.rlwy.net:34863/railway`
- threats 테이블: `id, severity, platform, content_preview, risk_score, status, detected_at`
- 매핑: `severity → ThreatRecord.category`, `content_preview → ThreatRecord.summary`, `risk_score → ThreatRecord.impact_score`

---

- [ ] **Step 1: requirements.txt에 패키지 추가**

`requirements.txt` 끝에 아래 두 줄 추가:
```
psycopg2-binary>=2.9
anthropic>=0.30
```

- [ ] **Step 2: 설치 확인**

```bash
pip install psycopg2-binary anthropic
```

Expected: 오류 없이 설치 완료.

- [ ] **Step 3: 테스트 먼저 작성**

`tests/test_db_source.py` 생성:

```python
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from cardnews.db_source import load_threats
from cardnews.models import ThreatRecord


def test_load_threats_falls_back_to_mock_when_no_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    records = load_threats()

    assert len(records) > 0
    assert all(isinstance(r, ThreatRecord) for r in records)


def test_load_threats_queries_db_when_database_url_set(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")

    fake_rows = [
        ("threat-db-1", "HIGH", "SNS에서 부정 리뷰가 확산되고 있습니다.", 8, date(2026, 6, 15)),
        ("threat-db-2", "MEDIUM", "커뮤니티에서 불만 게시글이 공유되고 있습니다.", 5, date(2026, 6, 14)),
    ]

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchall.return_value = fake_rows

    with patch("cardnews.db_source.psycopg2.connect", return_value=mock_conn):
        records = load_threats()

    assert len(records) == 2
    assert records[0].id == "threat-db-1"
    assert records[0].category == "HIGH"
    assert records[0].summary == "SNS에서 부정 리뷰가 확산되고 있습니다."
    assert records[0].impact_score == 8
    assert records[0].detected_at == date(2026, 6, 15)


def test_load_threats_falls_back_to_mock_on_db_error(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")

    with patch("cardnews.db_source.psycopg2.connect", side_effect=Exception("connection refused")):
        records = load_threats()

    assert len(records) > 0  # mock fallback
```

- [ ] **Step 4: 테스트가 실패하는지 확인**

```bash
cd C:\Users\A\OneDrive\Desktop\ai기말\card-news-pipeline
python -m pytest tests/test_db_source.py -v
```

Expected: `ImportError` 또는 `ModuleNotFoundError` (아직 `db_source.py` 없음).

- [ ] **Step 5: db_source.py 구현**

`cardnews/db_source.py` 생성:

```python
import os
from datetime import date

import psycopg2

from cardnews.mock_data import load_sample_threats
from cardnews.models import ThreatRecord

_QUERY = """
    SELECT
        id::text,
        severity,
        content_preview,
        risk_score::int,
        detected_at::date
    FROM threats
    WHERE content_preview IS NOT NULL
      AND detected_at >= NOW() - INTERVAL '14 days'
    ORDER BY risk_score DESC NULLS LAST
    LIMIT 20
"""


def load_threats() -> list[ThreatRecord]:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return load_sample_threats()

    try:
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(_QUERY)
                rows = cur.fetchall()

        if not rows:
            return load_sample_threats()

        return [
            ThreatRecord(
                id=str(row[0]),
                category=str(row[1]) if row[1] else "위협",
                summary=str(row[2]),
                impact_score=int(row[3]) if row[3] is not None else 5,
                detected_at=row[4] if isinstance(row[4], date) else date.today(),
            )
            for row in rows
        ]
    except Exception:
        return load_sample_threats()
```

- [ ] **Step 6: pipeline.py에서 mock_data 대신 db_source 사용**

`cardnews/pipeline.py`의 `from cardnews.mock_data import load_sample_threats` 줄을 교체:

```python
from pathlib import Path

from cardnews.db_source import load_threats
from cardnews.models import CardNewsScript
from cardnews.renderer import render_slides
from cardnews.scripter import generate_script
from cardnews.selector import select_best_candidate


def run_pipeline(
    output_dir: Path,
    used_ids: set[str] | None = None,
) -> CardNewsScript | None:
    records = load_threats()
    candidate = select_best_candidate(records, used_ids)

    if candidate is None:
        return None

    script = generate_script(candidate)
    render_slides(script, output_dir)
    return script
```

- [ ] **Step 7: 테스트 통과 확인**

```bash
python -m pytest tests/test_db_source.py tests/test_pipeline.py -v
```

Expected: 전부 PASS (pipeline 테스트는 DATABASE_URL 미설정이므로 mock 폴백).

- [ ] **Step 8: 커밋**

```bash
git add requirements.txt cardnews/db_source.py cardnews/pipeline.py tests/test_db_source.py
git commit -m "feat: add SAYbrand DB adapter with mock fallback"
```

---

## Task 2: LLM 기반 스크립팅 (Claude Haiku, mock 폴백)

**Files:**
- Create: `cardnews/llm_scripter.py`
- Modify: `cardnews/pipeline.py`
- Create: `tests/test_llm_scripter.py`

---

- [ ] **Step 1: 테스트 먼저 작성**

`tests/test_llm_scripter.py` 생성:

```python
from datetime import date
from unittest.mock import MagicMock, patch

from cardnews.llm_scripter import generate_script_with_llm
from cardnews.models import CardNewsScript, ThreatRecord

RECORD = ThreatRecord(
    id="threat-llm-test",
    detected_at=date(2026, 6, 16),
    category="HIGH",
    summary="SNS에서 부정 리뷰가 빠르게 확산되고 있습니다.",
    impact_score=9,
)


def test_generate_script_with_llm_falls_back_to_template_when_no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    script = generate_script_with_llm(RECORD)

    assert isinstance(script, CardNewsScript)
    assert script.source_id == RECORD.id
    assert len(script.slides) >= 3


def test_generate_script_with_llm_uses_claude_when_api_key_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

    llm_response_json = """{
        "title": "브랜드 위기, 당신의 차례가 될 수 있습니다",
        "slides": [
            {"headline": "충격적인 사건이 일어났습니다", "body": "SNS에서 부정 리뷰가 빠르게 확산되며 한 브랜드의 신뢰가 무너지기 시작했습니다."},
            {"headline": "왜 이렇게 빠르게 퍼질까요?", "body": "알고리즘은 부정 콘텐츠에 더 많은 노출을 줍니다. 몇 시간 만에 수만 명에게 도달합니다."},
            {"headline": "미리 알았다면 막을 수 있었습니다", "body": "SAYbrand는 이런 위협을 탐지 즉시 알려드립니다. 지금 무료로 시작하세요."}
        ],
        "description": "브랜드 리스크 실시간 감지 — SAYbrand와 함께 위기를 예방하세요.",
        "tags": ["브랜드리스크", "온라인평판", "위기관리", "마케팅", "SAYbrand"]
    }"""

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=llm_response_json)]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message

    with patch("cardnews.llm_scripter.anthropic.Anthropic", return_value=mock_client):
        script = generate_script_with_llm(RECORD)

    assert script.source_id == RECORD.id
    assert script.title == "브랜드 위기, 당신의 차례가 될 수 있습니다"
    assert len(script.slides) == 3
    assert script.slides[0].headline == "충격적인 사건이 일어났습니다"
    assert "SAYbrand" in script.tags or "브랜드리스크" in script.tags


def test_generate_script_with_llm_falls_back_on_invalid_json(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="이건 JSON이 아닙니다")]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message

    with patch("cardnews.llm_scripter.anthropic.Anthropic", return_value=mock_client):
        script = generate_script_with_llm(RECORD)

    # Should fall back to template
    assert isinstance(script, CardNewsScript)
    assert script.source_id == RECORD.id
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

```bash
python -m pytest tests/test_llm_scripter.py -v
```

Expected: `ImportError` (아직 `llm_scripter.py` 없음).

- [ ] **Step 3: llm_scripter.py 구현**

`cardnews/llm_scripter.py` 생성:

```python
import json
import os

import anthropic

from cardnews.models import CardNewsScript, Slide, ThreatRecord
from cardnews.scripter import generate_script

_MODEL = "claude-haiku-4-5-20251001"

_PROMPT_TEMPLATE = """다음 브랜드 위협 데이터를 바탕으로 유튜브 쇼츠용 카드뉴스 스크립트를 작성해주세요.

위협 유형: {category}
내용 요약: {summary}
위험 점수: {impact_score}/10

요구사항:
- 특정 브랜드/기업/개인을 식별할 수 없도록 반드시 가명화·일반화할 것
- 슬라이드 정확히 3장: (1) 훅/충격적 사실 (2) 왜 위험한가 (3) SAYbrand CTA
- 제목은 30자 이내, 각 슬라이드 본문은 60자 이내
- 태그는 5개, #없이 문자열만

반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "title": "...",
  "slides": [
    {{"headline": "...", "body": "..."}},
    {{"headline": "...", "body": "..."}},
    {{"headline": "...", "body": "..."}}
  ],
  "description": "...",
  "tags": ["...", "...", "...", "...", "..."]
}}"""


def generate_script_with_llm(record: ThreatRecord) -> CardNewsScript:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return generate_script(record)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": _PROMPT_TEMPLATE.format(
                        category=record.category,
                        summary=record.summary,
                        impact_score=record.impact_score,
                    ),
                }
            ],
        )
        raw = message.content[0].text.strip()
        data = json.loads(raw)
        return CardNewsScript(
            source_id=record.id,
            title=data["title"],
            slides=[Slide(headline=s["headline"], body=s["body"]) for s in data["slides"]],
            description=data["description"],
            tags=data["tags"],
        )
    except Exception:
        return generate_script(record)
```

- [ ] **Step 4: pipeline.py에서 llm_scripter 사용**

`cardnews/pipeline.py`의 `from cardnews.scripter import generate_script` 줄을 교체:

```python
from pathlib import Path

from cardnews.db_source import load_threats
from cardnews.llm_scripter import generate_script_with_llm
from cardnews.models import CardNewsScript
from cardnews.renderer import render_slides
from cardnews.selector import select_best_candidate


def run_pipeline(
    output_dir: Path,
    used_ids: set[str] | None = None,
) -> CardNewsScript | None:
    records = load_threats()
    candidate = select_best_candidate(records, used_ids)

    if candidate is None:
        return None

    script = generate_script_with_llm(candidate)
    render_slides(script, output_dir)
    return script
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
python -m pytest tests/test_llm_scripter.py tests/test_pipeline.py tests/test_scripter.py -v
```

Expected: 전부 PASS.

- [ ] **Step 6: 커밋**

```bash
git add cardnews/llm_scripter.py cardnews/pipeline.py tests/test_llm_scripter.py
git commit -m "feat: add Claude Haiku LLM scripter with template fallback"
```

---

## Task 3: YouTube 업로드 자동 재시도

**Files:**
- Modify: `cardnews/youtube_upload.py`
- Modify: `tests/test_youtube_upload.py`

---

재시도 정책: `HttpError` status 500/503에 한해 최대 3회, 대기 시간은 2→4→8초 (exponential backoff). 400/403/404는 재시도하지 않는다 (클라이언트 오류이므로 재시도해도 의미 없음).

- [ ] **Step 1: 재시도 테스트 추가**

`tests/test_youtube_upload.py` 끝에 아래 테스트 추가:

```python
from googleapiclient.errors import HttpError
from unittest.mock import call
import httplib2


def _http_error(status: int) -> HttpError:
    resp = httplib2.Response({"status": status})
    return HttpError(resp=resp, content=b"error")


def test_upload_video_retries_on_server_error_and_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr("cardnews.youtube_upload.time.sleep", lambda _: None)

    video_path = tmp_path / "threat-003.mp4"
    video_path.write_bytes(b"fake-mp4")
    status = _sample_status(str(video_path))

    mock_request = MagicMock()
    mock_request.next_chunk.side_effect = [
        _http_error(503),
        _http_error(503),
        (None, {"id": "retry-success"}),
    ]

    mock_youtube = MagicMock()
    mock_youtube.videos.return_value.insert.return_value = mock_request

    with patch("cardnews.youtube_upload.MediaFileUpload"):
        video_id = upload_video(mock_youtube, status, video_path)

    assert video_id == "retry-success"
    assert mock_request.next_chunk.call_count == 3


def test_upload_video_raises_after_max_retries(tmp_path, monkeypatch):
    monkeypatch.setattr("cardnews.youtube_upload.time.sleep", lambda _: None)

    video_path = tmp_path / "threat-003.mp4"
    video_path.write_bytes(b"fake-mp4")
    status = _sample_status(str(video_path))

    mock_request = MagicMock()
    mock_request.next_chunk.side_effect = _http_error(503)

    mock_youtube = MagicMock()
    mock_youtube.videos.return_value.insert.return_value = mock_request

    with patch("cardnews.youtube_upload.MediaFileUpload"):
        with pytest.raises(HttpError):
            upload_video(mock_youtube, status, video_path)

    assert mock_request.next_chunk.call_count == 4  # 1 + 3 retries


def test_upload_video_does_not_retry_on_client_error(tmp_path, monkeypatch):
    monkeypatch.setattr("cardnews.youtube_upload.time.sleep", lambda _: None)

    video_path = tmp_path / "threat-003.mp4"
    video_path.write_bytes(b"fake-mp4")
    status = _sample_status(str(video_path))

    mock_request = MagicMock()
    mock_request.next_chunk.side_effect = _http_error(403)

    mock_youtube = MagicMock()
    mock_youtube.videos.return_value.insert.return_value = mock_request

    with patch("cardnews.youtube_upload.MediaFileUpload"):
        with pytest.raises(HttpError):
            upload_video(mock_youtube, status, video_path)

    assert mock_request.next_chunk.call_count == 1  # 재시도 없음
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

```bash
python -m pytest tests/test_youtube_upload.py::test_upload_video_retries_on_server_error_and_succeeds -v
```

Expected: FAIL (재시도 로직 아직 없음).

- [ ] **Step 3: youtube_upload.py에 재시도 로직 추가**

`cardnews/youtube_upload.py` 전체를 아래로 교체:

```python
import os
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from cardnews.review_status import ReviewStatus

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
TOKEN_URI = "https://oauth2.googleapis.com/token"
_RETRYABLE_STATUS = {500, 503}
_MAX_RETRIES = 3


class YouTubeCredentialsError(RuntimeError):
    """필요한 YouTube OAuth 환경변수가 설정되지 않았을 때 발생."""


def build_youtube_client():
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")

    if not client_id or not client_secret or not refresh_token:
        raise YouTubeCredentialsError(
            "YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN 환경변수가 모두 설정되어야 합니다. "
            "youtube_auth_setup.py 스크립트로 발급받은 값을 .env에 설정해주세요."
        )

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=[YOUTUBE_UPLOAD_SCOPE],
    )
    credentials.refresh(Request())

    return build("youtube", "v3", credentials=credentials)


YOUTUBE_CATEGORY_ID = "25"  # News & Politics


def upload_video(youtube, status: ReviewStatus, video_path: Path) -> str:
    body = {
        "snippet": {
            "title": status.title,
            "description": status.description,
            "tags": status.tags,
            "categoryId": YOUTUBE_CATEGORY_ID,
        },
        "status": {
            "privacyStatus": "private",
        },
    }

    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    retry = 0
    response = None
    while response is None:
        try:
            _, response = request.next_chunk()
        except HttpError as error:
            if error.resp.status not in _RETRYABLE_STATUS or retry >= _MAX_RETRIES:
                raise
            time.sleep(2 ** retry)
            retry += 1

    return response["id"]


def set_thumbnail(youtube, video_id: str, thumbnail_path: Path) -> None:
    youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumbnail_path))).execute()
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_youtube_upload.py -v
```

Expected: 전부 PASS.

- [ ] **Step 5: 커밋**

```bash
git add cardnews/youtube_upload.py tests/test_youtube_upload.py
git commit -m "feat: add exponential backoff retry for YouTube upload failures"
```

---

## Task 4: Windows 작업 스케줄러 등록 스크립트

**Files:**
- Create: `schedule_task.ps1`

---

하루 3개 작업을 Windows 작업 스케줄러에 등록한다:
1. `run.py` — 오전 9시 (카드뉴스 생성 + Discord 검수 요청)
2. `check_review.py` — 오후 2시 (검수 결과 확인 + YouTube 업로드)
3. `health_check.py` — 오후 11시 (업로드 누락 감지 + 알림)

- [ ] **Step 1: schedule_task.ps1 생성**

프로젝트 루트에 `schedule_task.ps1` 생성:

```powershell
# card-news-pipeline Windows 작업 스케줄러 등록 스크립트
# 실행: PowerShell을 관리자 권한으로 열고 .\schedule_task.ps1 실행

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = (Get-Command python).Source

$tasks = @(
    @{
        Name    = "CardNews-Generate"
        Script  = "run.py"
        Hour    = 9
        Minute  = 0
        Comment = "카드뉴스 생성 및 Discord 검수 요청"
    },
    @{
        Name    = "CardNews-CheckReview"
        Script  = "check_review.py"
        Hour    = 14
        Minute  = 0
        Comment = "Discord 검수 확인 및 YouTube 업로드"
    },
    @{
        Name    = "CardNews-HealthCheck"
        Script  = "health_check.py"
        Hour    = 23
        Minute  = 0
        Comment = "업로드 누락 감지 및 알림"
    }
)

foreach ($task in $tasks) {
    $scriptPath = Join-Path $ProjectRoot $task.Script
    $action = New-ScheduledTaskAction `
        -Execute $Python `
        -Argument $scriptPath `
        -WorkingDirectory $ProjectRoot

    $trigger = New-ScheduledTaskTrigger `
        -Daily `
        -At "$($task.Hour):$($task.Minute.ToString('D2'))"

    $settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
        -RestartCount 1 `
        -RestartInterval (New-TimeSpan -Minutes 5)

    Register-ScheduledTask `
        -TaskName $task.Name `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description $task.Comment `
        -Force | Out-Null

    Write-Host "등록 완료: $($task.Name) — 매일 $($task.Hour):$($task.Minute.ToString('D2'))"
}

Write-Host ""
Write-Host "작업 스케줄러 등록 완료. 확인하려면: Get-ScheduledTask -TaskName 'CardNews-*'"
Write-Host "환경변수(.env)가 시스템 환경변수로 설정되어 있어야 스케줄러에서도 동작합니다."
```

- [ ] **Step 2: 전체 테스트 스위트 통과 확인**

```bash
python -m pytest -v
```

Expected: 전부 PASS (skipped 1건은 정상).

- [ ] **Step 3: 커밋**

```bash
git add schedule_task.ps1
git commit -m "feat: add Windows Task Scheduler registration script"
```

---

## Task 5: 전체 통합 검증

- [ ] **Step 1: 전체 테스트 최종 확인**

```bash
python -m pytest -v --tb=short
```

Expected: 모든 테스트 PASS (skipped 1건은 허용).

- [ ] **Step 2: DB 연결 실제 확인 (선택 — 실제 DB 접근 필요)**

```bash
set DATABASE_URL=postgresql://readonly_user:brand0192@zephyr.proxy.rlwy.net:34863/railway
python -c "from cardnews.db_source import load_threats; r = load_threats(); print(f'{len(r)}건 로드됨'); print(r[0])"
```

Expected: DB에서 위협 레코드가 로드되어 출력됨. 오류 시 mock 폴백 동작.

- [ ] **Step 3: 메모리 업데이트**

프로젝트 메모리(`project_card_news_pipeline.md`)의 진행 상태를 현재 커밋 해시로 업데이트.

- [ ] **Step 4: 최종 커밋 태그 (선택)**

```bash
git tag v1.0-pipeline-complete
```
