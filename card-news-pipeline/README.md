# card-news-pipeline

SAYbrand가 탐지한 브랜드 리스크 사례를 카드뉴스(슬라이드 이미지 + 9:16 영상)로 자동 생성하고, Discord로 검수 요청을 보내는 파이프라인입니다.

## 설치

```bash
pip install -r requirements.txt
playwright install chromium
```

### ffmpeg 설치 (영상 합성에 필요)

- Windows: `winget install ffmpeg` 실행 후 새 터미널에서 `ffmpeg -version`으로 설치 확인
- 또는 https://ffmpeg.org/download.html 에서 다운로드 후 PATH에 등록

ffmpeg가 없으면 슬라이드 이미지까지는 생성되지만 영상 합성 단계에서 안내 메시지와 함께 중단됩니다.

## 환경변수 설정 (Discord 검수)

`.env.example`을 참고해 아래 값을 환경변수로 설정합니다 (PowerShell 예시):

```powershell
$env:DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/..."
$env:DISCORD_BOT_TOKEN = "..."
```

- `DISCORD_WEBHOOK_URL`: 검수용 비공개 채널의 Incoming Webhook URL
- `DISCORD_BOT_TOKEN`: 같은 채널에 "메시지 보기/메시지 기록 보기" 권한으로 초대된 봇의 토큰 (반응 감지용)

설정하지 않으면 영상까지는 생성되고, Discord 검수 요청은 건너뜁니다.

## BGM (배경음악)

`assets/bgm/` 폴더에 저작권 무료 mp3 파일을 넣으면 자동으로 사용됩니다. 자세한 내용은 `assets/bgm/README.md` 참고.

## YouTube 업로드 설정

승인된 카드뉴스 영상은 YouTube Data API v3로 **비공개(private)** 업로드됩니다.

1. [Google Cloud Console](https://console.cloud.google.com/)에서 새 프로젝트를 만들고 "YouTube Data API v3"를 활성화합니다.
2. "OAuth 동의 화면"을 구성하고, "사용자 인증 정보"에서 OAuth 클라이언트 ID(애플리케이션 유형: **데스크톱 앱**)를 만듭니다.
3. 클라이언트 정보를 `client_secret.json`으로 다운로드해 프로젝트 루트에 둡니다 (이 파일은 `.gitignore`에 포함되어 커밋되지 않습니다).
4. 다음 명령으로 리프레시 토큰을 발급받습니다:
   ```bash
   python youtube_auth_setup.py
   ```
5. 출력된 값을 환경변수로 설정합니다 (PowerShell 예시):
   ```powershell
   $env:YOUTUBE_CLIENT_ID = "..."
   $env:YOUTUBE_CLIENT_SECRET = "..."
   $env:YOUTUBE_REFRESH_TOKEN = "..."
   ```

설정하지 않으면 검수 승인 후 업로드 단계에서 안내 메시지와 함께 건너뜁니다.

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

## 사용법

1. 카드뉴스 생성 + 영상 합성 + Discord 검수 요청:
   ```bash
   python run.py
   ```
2. Discord에서 ✅(승인) 또는 ❌(반려) 반응을 남깁니다.
3. 검수 결과 확인 및 처리 (승인/반려/재시도):
   ```bash
   python check_review.py
   ```
   - 승인: YouTube에 비공개로 업로드하고, 첫 슬라이드를 썸네일로 등록
   - 반려(1차): 다음 후보로 영상을 재생성하고 다시 Discord에 검수 요청
   - 반려(2차, 재시도 후에도 반려): 미발행 처리, 알림 메시지만 출력
4. (선택, 1일 1회) 오늘 업로드 성공 여부 점검:
   ```bash
   python health_check.py
   ```
