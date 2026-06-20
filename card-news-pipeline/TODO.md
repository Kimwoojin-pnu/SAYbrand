# card-news-pipeline — 남은 작업 목록

> **현재 상태 (2026-06-19 기준)**
> - 코어 파이프라인 100% 완성: DB 연동 → LLM 스크립트 → 슬라이드 렌더링 → MP4 합성
> - 테스트: 92 passed / 1 skipped
> - 남은 것은 **외부 서비스 연결 3가지** 뿐 (코드는 이미 완성되어 있음)

---

## 프로젝트 구조 (핵심만)

```
card-news-pipeline/
├── run.py                  # 진입점: 생성 + Discord 검수 요청
├── check_review.py         # 검수 결과 확인 + YouTube 업로드
├── youtube_auth_setup.py   # YouTube OAuth 토큰 발급용 1회성 스크립트
├── cardnews/
│   ├── alerts.py           # Discord 실패 알림 (DISCORD_ALERT_WEBHOOK_URL)
│   ├── discord_review.py   # Discord 검수 전송 + 반응 조회
│   ├── orchestrator.py     # 전체 흐름 조율
│   ├── youtube_upload.py   # YouTube 업로드 + 썸네일
│   └── ...
├── assets/bgm/             # 배경음악 mp3 파일 넣는 곳
└── output/                 # 생성된 슬라이드·영상·로그 저장 위치
```

---

## Task 1 — Discord Webhook 연결

**목적**: 생성된 카드뉴스를 Discord 채널로 전송해 ✅/❌ 반응으로 검수

### 필요한 환경변수

| 변수명 | 용도 | 없으면? |
|--------|------|---------|
| `DISCORD_WEBHOOK_URL` | 검수용 채널 Incoming Webhook URL | 검수 요청 건너뜀 |
| `DISCORD_BOT_TOKEN` | 봇 토큰 (반응 감지용) | `check_review.py` 실행 불가 |
| `DISCORD_ALERT_WEBHOOK_URL` | 실패 알림용 채널 Webhook URL (선택) | 실패 알림 건너뜀 |

### 설정 절차

1. **Discord 서버에 채널 2개 만들기**
   - `#카드뉴스-검수` (검수용)
   - `#파이프라인-알림` (실패 알림용, 선택)

2. **Incoming Webhook 생성**
   - `#카드뉴스-검수` → 채널 설정 → 연동 → 웹후크 → 새 웹후크 → URL 복사
   - 같은 방식으로 `#파이프라인-알림`도 생성 (선택)

3. **Discord 봇 생성 (반응 감지용)**
   - https://discord.com/developers/applications → New Application
   - Bot 탭 → Reset Token → 토큰 복사
   - OAuth2 → URL Generator → scope: `bot`, permission: `Read Messages` + `Read Message History`
   - 생성된 URL로 봇을 `#카드뉴스-검수` 채널이 있는 서버에 초대

4. **환경변수 설정** (PowerShell)
   ```powershell
   $env:DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/..."
   $env:DISCORD_BOT_TOKEN = "Bot토큰여기"
   $env:DISCORD_ALERT_WEBHOOK_URL = "https://discord.com/api/webhooks/..."
   ```

5. **테스트**
   ```bash
   python run.py
   ```
   Discord 채널에 슬라이드 이미지와 메시지가 올라오면 성공.

### 관련 코드
- `cardnews/discord_review.py` — `send_preview()`, `check_reaction()`
- `cardnews/alerts.py` — `send_alert()`
- `cardnews/orchestrator.py:50` — `request_review()` (DISCORD_WEBHOOK_URL 없으면 None 반환)

---

## Task 2 — YouTube OAuth 설정

**목적**: 검수 승인된 영상을 YouTube에 비공개(private) 업로드

### 필요한 환경변수

| 변수명 | 용도 |
|--------|------|
| `YOUTUBE_CLIENT_ID` | OAuth 클라이언트 ID |
| `YOUTUBE_CLIENT_SECRET` | OAuth 클라이언트 시크릿 |
| `YOUTUBE_REFRESH_TOKEN` | 리프레시 토큰 |

### 설정 절차

1. **Google Cloud Console 프로젝트 생성**
   - https://console.cloud.google.com/
   - 새 프로젝트 생성 (예: `card-news-pipeline`)

2. **YouTube Data API v3 활성화**
   - API 및 서비스 → 라이브러리 → "YouTube Data API v3" 검색 → 사용 설정

3. **OAuth 동의 화면 구성**
   - API 및 서비스 → OAuth 동의 화면
   - User Type: **외부** (개인 계정이면 외부 선택)
   - 앱 이름, 이메일 입력 후 저장
   - 테스트 사용자에 본인 Google 계정 이메일 추가

4. **OAuth 클라이언트 ID 생성**
   - API 및 서비스 → 사용자 인증 정보 → 사용자 인증 정보 만들기 → OAuth 클라이언트 ID
   - 애플리케이션 유형: **데스크톱 앱**
   - 생성 후 `client_secret.json` 다운로드
   - 파일을 `card-news-pipeline/` 루트에 저장 (`.gitignore`에 이미 포함됨)

5. **리프레시 토큰 발급**
   ```bash
   python youtube_auth_setup.py
   ```
   브라우저가 열리면 YouTube 채널이 있는 Google 계정으로 로그인 → 권한 허용

6. **출력된 값을 환경변수로 설정** (PowerShell)
   ```powershell
   $env:YOUTUBE_CLIENT_ID = "출력된값"
   $env:YOUTUBE_CLIENT_SECRET = "출력된값"
   $env:YOUTUBE_REFRESH_TOKEN = "출력된값"
   ```

7. **테스트**
   ```bash
   # 먼저 run.py로 영상 생성 + Discord 검수 요청
   python run.py

   # Discord에서 ✅ 반응 후
   python check_review.py
   ```
   YouTube Studio에서 비공개 영상이 업로드된 것을 확인.

### 관련 코드
- `cardnews/youtube_upload.py` — `build_youtube_client()`, `upload_video()`, `set_thumbnail()`
- `youtube_auth_setup.py` — 1회성 토큰 발급 스크립트

---

## Task 3 — BGM 파일 추가 (선택)

**목적**: 영상에 배경음악 자동 삽입

### 절차

1. 저작권 무료 mp3 파일 구하기
   - 추천: YouTube Audio Library, pixabay.com/music, freesound.org
   - 9:16 숏폼에 어울리는 잔잔한 배경음악

2. 파일을 `assets/bgm/` 폴더에 넣기
   ```
   assets/bgm/background.mp3
   ```
   여러 개 넣으면 알파벳 순 첫 번째 파일 자동 사용

3. 별도 설정 없음 — `run.py` 실행 시 자동으로 감지해서 믹싱

### 관련 코드
- `cardnews/video.py` — ffmpeg BGM 믹싱 로직
- `cardnews/orchestrator.py:22` — `_find_bgm()` 함수

---

## 전체 플로우 요약

```
python run.py
  → SAYbrand DB에서 오늘 위협 데이터 조회
  → Claude Haiku로 스크립트 생성
  → Playwright로 슬라이드 PNG 렌더링
  → ffmpeg로 MP4 합성 (BGM 있으면 믹싱)
  → Discord #카드뉴스-검수 채널로 전송
  → output/review_status.json 저장

[Discord에서 ✅ 또는 ❌ 반응]

python check_review.py
  → DISCORD_BOT_TOKEN으로 반응 조회
  → ✅ 승인: YouTube 비공개 업로드 + 썸네일 등록
  → ❌ 반려(1차): 다음 후보로 재생성 + 재검수 요청
  → ❌ 반려(2차): 미발행 처리 + 알림
```

---

## 환경변수 전체 목록

```powershell
# SAYbrand DB (이미 설정됨)
$env:DATABASE_URL = "postgresql://readonly_user:brand0192@zephyr.proxy.rlwy.net:34863/railway"

# Anthropic (LLM 스크립트, 없으면 템플릿 fallback)
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Discord 검수 (Task 1)
$env:DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/..."
$env:DISCORD_BOT_TOKEN = "..."
$env:DISCORD_ALERT_WEBHOOK_URL = "https://discord.com/api/webhooks/..."  # 선택

# YouTube (Task 2)
$env:YOUTUBE_CLIENT_ID = "..."
$env:YOUTUBE_CLIENT_SECRET = "..."
$env:YOUTUBE_REFRESH_TOKEN = "..."
```
