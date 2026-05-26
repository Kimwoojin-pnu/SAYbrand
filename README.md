# SAYbrand

브랜드 리스크를 실시간으로 감지·분석하는 AI 대시보드.

## 로컬 실행

```bash
pip install -r requirements.txt
cp .env .env.local   # .env에 키 입력 후 실행
uvicorn main:app --reload
```

`http://localhost:8000` 접속 → 미로그인 시 `/login` 으로 자동 리다이렉트.

## 환경변수 설정 (.env)

| 키 | 설명 |
|---|---|
| `GOOGLE_CLIENT_ID` | Google OAuth 앱 클라이언트 ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth 앱 클라이언트 시크릿 |
| `GOOGLE_REDIRECT_URI` | OAuth 콜백 URI (로컬: `http://localhost:8000/auth/callback`) |
| `SESSION_SECRET_KEY` | 세션 서명 키 — 운영에서 반드시 강한 랜덤 문자열로 교체 |
| `ANTHROPIC_API_KEY` | Claude Haiku L3 분석 (없으면 Mock으로 동작) |
| `GEMINI_API_KEY` | Gemini Flash L2 분석 (없으면 Mock으로 동작) |
| `POLAR_ACCESS_TOKEN` | Polar.sh API 토큰 |
| `POLAR_WEBHOOK_SECRET` | Polar.sh Webhook 서명 시크릿 |
| `POLAR_PRODUCT_ID` | Polar.sh 결제 상품 ID |

## Google OAuth 앱 등록

1. [Google Cloud Console](https://console.cloud.google.com/) → API 및 서비스 → 사용자 인증 정보
2. OAuth 2.0 클라이언트 ID 생성 (웹 애플리케이션)
3. 승인된 리다이렉션 URI 추가:
   - 로컬: `http://localhost:8000/auth/callback`
   - 운영: `https://<your-domain>/auth/callback`
4. 클라이언트 ID와 시크릿을 `.env`에 입력

## 배포 구조

| 서비스 | 역할 | 플랫폼 |
|---|---|---|
| FastAPI | 대시보드, API, 인증, 결제 | Vercel |
| Celery Worker | 데이터 수집, AI 분석, 알림 | Railway |
| PostgreSQL | 메인 데이터베이스 | Railway (플러그인) |
| Redis | 메시지 큐 + 캐싱 | Railway (플러그인) |

## Railway 배포 순서

1. Railway 프로젝트 생성
2. PostgreSQL 플러그인 추가 → DATABASE_URL 자동 발급
3. Redis 플러그인 추가 → REDIS_URL 자동 발급
4. 환경변수 등록:
   - `DATABASE_URL` — Railway PostgreSQL URL (자동 발급)
   - `REDIS_URL` / `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` — Railway Redis URL
   - `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`
   - `X_BEARER_TOKEN`, `YOUTUBE_API_KEY`, `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`
   - `RAILWAY_ENVIRONMENT=true`
5. GitHub 연결 → 자동 배포 (`railway.toml` 기준으로 워커 실행)

## Vercel 배포 체크리스트

```
□ Vercel 프로젝트 생성 (GitHub 저장소 연결)
□ Vercel 대시보드 → Settings → Environment Variables에 .env 키 전부 등록
□ DATABASE_URL: Railway PostgreSQL URL 동일하게
□ REDIS_URL / CELERY_BROKER_URL / CELERY_RESULT_BACKEND: Railway Redis URL 동일하게
□ GOOGLE_REDIRECT_URI를 Vercel 도메인으로 변경
    예: https://saybrand.vercel.app/auth/callback
□ Google OAuth 앱 → 승인된 리다이렉션 URI에 Vercel 도메인 추가
□ SESSION_SECRET_KEY를 강한 랜덤 값으로 교체
□ POLAR_WEBHOOK_SECRET 등록 후 Polar.sh Webhook URL을
    https://<vercel-domain>/billing/webhook 으로 설정
□ vercel deploy 실행
```

> **Vercel SQLite 주의사항**
> Vercel 파일시스템은 `/tmp`만 쓰기 가능하며 재배포 시 초기화됩니다.
> Railway PostgreSQL을 DATABASE_URL로 설정하면 영속 데이터베이스로 동작합니다.

## 로컬 개발 (Docker)

PostgreSQL + Redis + Celery 워커를 한 번에 실행:

```bash
# 전체 스택 실행 (PostgreSQL + Redis + Worker + Flower)
docker-compose up -d

# FastAPI만 별도 실행 (핫리로드)
uvicorn main:app --reload

# Flower (Celery 모니터링) 접속
open http://localhost:5555
```

PostgreSQL / Redis 없이 SQLite만으로도 개발 가능:
```env
DATABASE_URL=sqlite+aiosqlite:///./brandguard.db
# REDIS_URL 미설정 시 Celery 없이 /api/dashboard/scan 직접 실행
```

## MVP 완료 기준

- [x] `uvicorn main:app --reload` 에러 없이 기동
- [x] `http://localhost:8000` → 미로그인 시 `/login` 리다이렉트
- [x] Google 로그인 성공 시 대시보드 진입
- [x] 위협 목록 API (`/api/dashboard/threats`) 정상 응답
- [x] 리스크 스코어 게이지 표시
- [x] 위협 클릭 → 상세 모달 → 상태 변경 동작
- [x] Polar.sh webhook 수신 시 DB subscription_status 업데이트
- [x] `vercel.json` 있고 `vercel deploy`로 배포 가능한 상태
- [x] API 키 없어도 Mock으로 정상 동작
