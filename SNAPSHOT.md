# SAYbrand — Snapshot (2026-05-18 v3)

## 1. 완료된 파일

| 경로 | 설명 |
|---|---|
| `main.py` | SessionMiddleware, auth/billing/profile/dashboard 라우터, /login·/settings 보호 라우트 |
| `backend/config.py` | Google OAuth·Polar·DART·AI 키, Vercel DB 경로 분기, celery_broker_url·celery_result_backend·is_vercel·is_railway 추가, is_production/is_local/can_run_workers/db_url_safe 프로퍼티 |
| `backend/db/database.py` | SQLite/PostgreSQL 엔진 자동 분기, AsyncSession, get_db, init_db() |
| `backend/db/seed.py` | 앱 시작 시 Mock 위협 데이터 자동 삽입 |
| `backend/models/orm.py` | User·Threat·Alert·Keyword + CustomerProfile·CustomerAlias·CustomerSocialAccount·CustomerExecutive |
| `backend/models/schemas.py` | ThreatBase·RiskScoreResponse·UserOut + CustomerProfile 계열·EntityResolverResult·DartLookupResult·WikidataLookupResult |
| `backend/routers/dashboard.py` | /api/dashboard/* — stats·risk-score·threats·alerts·상태변경·trend·platform-stats·scan(Celery분기)·scan-local |
| `backend/routers/auth.py` | /auth/login·callback·logout·me — Google OAuth 2.0 + 세션 |
| `backend/routers/billing.py` | /billing/checkout·webhook — Polar.sh + HMAC 검증 |
| `backend/routers/profile.py` | /api/profile CRUD + aliases·social-accounts·executives + DART·Wikidata 엔리치먼트 |
| `backend/middleware/auth.py` | get_current_user — 세션 확인, 미인증 시 401 |
| `backend/services/risk_scorer.py` | recency_weight(시간 감쇠)·velocity_bonus(확산속도) 적용 리스크 스코어 |
| `backend/services/profile_enricher.py` | DART API(상장사 정보)·Wikidata API(로고·SNS 핸들) 자동 조회 |
| `backend/services/entity_resolver.py` | alias 가중치 매칭 relevance_score 0~1, 공식 계정 오탐 자동 제외 |
| `backend/services/analyzers/l3_deep.py` | Claude Haiku 4.5 심층 분석, 고객 프로파일 컨텍스트 시스템 프롬프트 주입 |
| `backend/workers/celery_app.py` | Celery 앱 설정 + beat 스케줄 4개(30분 수집·일간·주간 리포트·90일 만료 삭제) |
| `backend/workers/collection_tasks.py` | collect_all_profiles·collect_single_profile·purge_expired_data 태스크 |
| `backend/workers/analysis_tasks.py` | analyze_threat — L3 심층 분석 비동기 태스크 |
| `backend/workers/alert_tasks.py` | send_immediate_alert·send_daily_reports·send_weekly_reports 태스크 |
| `frontend/pages/login.html` | Google 로그인 버튼, 에러 메시지 처리 |
| `frontend/pages/dashboard.html` | KPI·게이지·위협목록·상세패널·로그아웃·동적 사용자 정보 |
| `frontend/pages/settings.html` | 고객 프로파일 온보딩 UI — 탭 4개(기본정보·이름변형·공식계정·임직원) |
| `frontend/assets/js/api.js` | /api/dashboard/* fetch 래퍼 |
| `frontend/assets/js/dashboard.js` | 대시보드 UI 전체 로직 |
| `frontend/assets/css/custom.css` | 폰트(Syne·Noto Sans KR·JetBrains Mono), 디자인 토큰 |
| `requirements.txt` | fastapi·sqlalchemy·authlib·itsdangerous·polar-sdk·asyncpg·alembic·celery[redis]·flower 등 |
| `vercel.json` | Vercel serverless 배포 설정, maxDuration 60s |
| `railway.toml` | Railway Celery 워커 배포 설정 |
| `Procfile` | worker / beat / flower 프로세스 정의 |
| `docker-compose.yml` | postgres + redis + worker + flower 로컬 환경 |
| `.env` / `.env.example` | 환경변수 파일 / 커밋용 템플릿 |
| `.gitignore` | .env·*.db·__pycache__·venv 제외 |

## 2. .env 필요 키

```
# 기본
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI        # 로컬: http://localhost:8000/auth/callback
SESSION_SECRET_KEY         # 랜덤 강한 문자열 필수

# DB / Redis (로컬은 기본값으로 SQLite·Redis localhost 사용)
DATABASE_URL               # 로컬: sqlite+aiosqlite:///./brandguard.db
                           # 프로덕션: postgresql+asyncpg://... (Railway 자동 발급)
REDIS_URL                  # redis://localhost:6379/0
CELERY_BROKER_URL          # redis://localhost:6379/1
CELERY_RESULT_BACKEND      # redis://localhost:6379/2

# AI / 수집 (선택 — 없으면 Mock)
ANTHROPIC_API_KEY
GEMINI_API_KEY
GOOGLE_VISION_API_KEY
DART_API_KEY
NAVER_CLIENT_ID
NAVER_CLIENT_SECRET
X_BEARER_TOKEN
YOUTUBE_API_KEY

# 결제
POLAR_ACCESS_TOKEN
POLAR_WEBHOOK_SECRET
POLAR_PRODUCT_ID

# SMTP 알림 (선택)
SMTP_HOST
SMTP_USER
SMTP_PASSWORD

# 환경 식별 (배포 플랫폼이 자동 주입)
VERCEL                     # Vercel이 자동 주입
RAILWAY_ENVIRONMENT        # Railway에서 true로 설정
```

## 3. DB 스키마

```
users                id, name, email, company, user_type, google_id, avatar_url,
                     polar_customer_id, subscription_status, subscription_tier, created_at

threats              id, user_id(FK), module, threat_type, severity, platform,
                     source_account, source_url, content_preview, confidence,
                     risk_score, ai_analysis, ai_response_suggestion, status,
                     post_published_at, engagements_per_hour, detected_at, updated_at

alerts               id, threat_id(FK), severity, message, channel, sent_at

keywords             id, user_id(FK), keyword, platforms(JSON), active, created_at

customer_profiles    id, user_id(FK), profile_type, display_name, industry,
                     description, logo_url, dart_corp_code, wikidata_id, created_at

customer_aliases     id, profile_id(FK), alias, alias_type, weight

customer_social_accounts  id, profile_id(FK), platform, handle, verified

customer_executives  id, profile_id(FK), name, role, photo_url, priority
```

## 4. 아키텍처 — Vercel + Railway 분리

```
Vercel (FastAPI)              Railway (Celery Worker)
────────────────────          ──────────────────────────
사용자 요청 응답               30분마다 수집 자동 실행
대시보드 렌더링                AI 분석 파이프라인 (L2/L3)
인증 / 결제                   이메일 알림 발송
"스캔 실행" 버튼 →            ← 태스크 받아서 실제 실행
조회 API                      결과를 PostgreSQL에 저장
                              Redis 메시지 큐 사용
```

**로컬 환경**: SQLite + Redis 없이도 동작 (Celery 없이 `/api/dashboard/scan` 직접 실행)

## 5. 에러 / TODO

- `GOOGLE_CLIENT_ID/SECRET` 미입력 시 `/auth/login` OAuth 에러 (정상 동작)
- `SESSION_SECRET_KEY` 기본값 → 운영 전 반드시 교체
- `billing.py` Polar.sh 실계정 검증 필요
- collectors(instagram·youtube·x·tiktok·naver)·l1/l2 분석기 미구현 → Mock 데이터로 동작
- `backend/workers/collection_tasks.py` — `ProfileLoader`, `collect_for_profile`, `run_pipeline` 서비스 미구현 (워커 파일은 완성, 의존 서비스 stub 상태)
- `frontend/pages/threats.html`, `reports.html` 미생성
- Celery Beat 스케줄: 코드 완성, Redis 연결 시 실제 동작 (로컬 Redis 없으면 기동 불가)

## 6. 마지막 수정 파일 (2026-05-18 STACK_UPDATE)

| 파일 | 변경 내용 |
|---|---|
| `requirements.txt` | asyncpg·alembic·celery[redis]·flower 추가 |
| `backend/config.py` | celery_broker_url·celery_result_backend·is_vercel·is_railway 필드, 프로퍼티 4개 추가 |
| `backend/db/database.py` | SQLite/PostgreSQL 엔진 분기, init_db() 추가 |
| `backend/workers/celery_app.py` | 신규 — Celery 앱 + beat 스케줄 |
| `backend/workers/collection_tasks.py` | 신규 — 수집 태스크 3개 |
| `backend/workers/analysis_tasks.py` | 신규 — L3 분석 태스크 |
| `backend/workers/alert_tasks.py` | 신규 — 알림 태스크 3개 |
| `backend/routers/dashboard.py` | POST /scan Celery 분기, POST /scan-local 추가 |
| `vercel.json` | maxDuration: 60 추가 |
| `railway.toml` | 신규 — Railway 배포 설정 |
| `Procfile` | 신규 — worker·beat·flower 프로세스 |
| `docker-compose.yml` | 신규 — 로컬 전체 스택 |
| `README.md` | 배포 구조·Railway/Vercel 배포 순서·Docker 로컬 개발 섹션 추가 |

## 7. 실행 상태 (2026-05-18 확인)

- `python -m uvicorn main:app --reload` ✅ 정상 기동
- `/api/dashboard/stats` ✅ Mock 15건 응답
- `python -m pytest tests/ -v` ✅ 46/46 통과
- `from backend.workers.celery_app import celery_app` ✅ import 성공
- Celery 워커 실제 기동: Redis 필요 (`celery -A backend.workers.celery_app worker`)
