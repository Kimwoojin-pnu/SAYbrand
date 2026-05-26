# SAYbrand 진행 상황

**마지막 업데이트: 2026-05-26**
**평가 기준: ✅ 실제 end-to-end 동작 / 🟡 Mock / ❌ 미구현 / ⚠️ 불안정**

---

## 인프라 / 설정

| 항목 | 상태 | 비고 |
|------|------|------|
| `backend/config.py` | ✅ | YouTube, SMTP 키 추가됨 |
| `backend/db/database.py` | ✅ | AsyncSession, aiosqlite |
| `backend/db/seed.py` | 🟡 | Mock 위협 15건 자동 삽입 |
| `main.py` | ✅ | Rate limiter, keywords, reports 라우터 등록 |
| `requirements.txt` | ✅ | |
| `vercel.json` | ⚠️ | maxDuration 60s 추가, 실 배포 미검증 |
| `railway.toml` | ✅ | Celery 워커 배포 설정 |
| `Procfile` | ✅ | worker/beat/flower 프로세스 |
| `docker-compose.yml` | ✅ | postgres+redis+worker+flower 로컬 환경 |
| `.env` | ✅ | 모든 키 항목 포함 (값은 사용자 입력 필요) |

---

## 데이터 수집기

| 항목 | 상태 | 비고 |
|------|------|------|
| `collectors/base.py` | ✅ | RawPost, make_post(is_mock=), BaseCollector |
| `collectors/compliance.py` | ✅ | robots.txt 체크, PII 마스킹, RateLimiter (2초) |
| `collectors/naver.py` | ✅ 키 있을때 / 🟡 없을때 | NAVER_CLIENT_ID 입력 시 실제 수집 **검증완료** (2026-05-26: 삼성 키워드 25건 수집·3건 위협 분류) |
| `collectors/x_twitter.py` | ✅ 키 있을때 / 🟡 없을때 | X_BEARER_TOKEN 입력 시 실제 수집, remove_pii 적용 |
| `collectors/youtube.py` | ✅ 키 있을때 / 🟡 없을때 | YOUTUBE_API_KEY 입력 시 실제 수집, remove_pii 적용 |
| `collectors/community_kr.py` | 🟡 | 에펨/더쿠/클리앙/루리웹/인스티즈/나무위키, robots.txt 자동 차단 |
| `collectors/orchestrator.py` | ✅ | 프로파일 키워드 기반 전 플랫폼 병렬 수집 |
| `collectors/instagram.py` | ❌ | 미구현 (API 접근 제한으로 보류) |
| `collectors/tiktok.py` | ❌ | 미구현 (API 접근 제한으로 보류) |

---

## AI 분석기

| 항목 | 상태 | 비고 |
|------|------|------|
| `analyzers/keyword_database.py` | ✅ | 900개+ 키워드, 18개 카테고리 |
| `analyzers/l1_filter.py` | ✅ | 키워드 기반, score 0~1 반환 |
| `analyzers/l2_text.py` | ✅ 키 있을때 / 🟡 없을때 | HyperCLOVA→Gemini→Mock 폴백, is_mock 명시 |
| `analyzers/l2_image.py` | ✅ | LogoSimilarityEngine (pHash 해밍 거리) |
| `analyzers/l3_deep.py` | ✅ 키 있을때 / 🟡 없을때 | Claude Haiku 4.5, ANTHROPIC_API_KEY 필요 |
| `analyzers/l2_cost_tracker.py` | ✅ | UsageLog DB 기록 |

---

## 분석 파이프라인

| 항목 | 상태 | 비고 |
|------|------|------|
| `services/pipeline.py` | ✅ | L1→L2→L3→DB 저장, is_mock 전파 |
| `POST /api/dashboard/scan` | ✅ | Vercel→Celery 태스크 발행 / 로컬→직접 실행 분기 |
| `POST /api/dashboard/scan-local` | ✅ | 로컬 전용 직접 실행 (Vercel에서 403) |
| `GET /api/dashboard/scan` | 🟡 | 레거시 키워드 스캔 엔드포인트 |

---

## 비동기 워커 (Celery)

| 항목 | 상태 | 비고 |
|------|------|------|
| `workers/celery_app.py` | ✅ | beat 스케줄 4개 (30분 수집·일간·주간 리포트·90일 만료 삭제) |
| `workers/collection_tasks.py` | ✅ | collect_all_profiles·collect_single_profile·purge_expired_data |
| `workers/analysis_tasks.py` | ✅ | analyze_threat — L3 심층 분석 태스크 |
| `workers/alert_tasks.py` | ✅ | send_immediate_alert·send_daily_reports·send_weekly_reports |
| Celery 실제 기동 | 🟡 | Redis 필요 (`celery -A backend.workers.celery_app worker`) |

---

## 라우터 / API

| 항목 | 상태 | 비고 |
|------|------|------|
| `routers/dashboard.py` | ✅ | stats, risk-score, threats, alerts, trend, platform-stats, scan |
| `routers/auth.py` | ⚠️ | 코드 구현됨, GOOGLE_CLIENT_ID 없으면 OAuth 불가 |
| `routers/billing.py` | ⚠️ | Polar.sh 코드 구현됨, 실 결제 미검증 |
| `routers/profile.py` | ✅ | CustomerProfile CRUD + 서브리소스 |
| `routers/keywords.py` | ✅ | GET/POST/DELETE /api/keywords |
| `routers/reports.py` | ✅ | /api/reports/daily, /api/reports/weekly |

---

## 미들웨어 / 서비스

| 항목 | 상태 | 비고 |
|------|------|------|
| `middleware/auth.py` | ✅ | get_current_user, 401 반환 |
| `middleware/rate_limiter.py` | ✅ | 분당 60회 / 스캔 시간당 10회 |
| `services/risk_scorer.py` | ✅ | 가중치 + 업종/임직원 가중치, classify_alert_threshold |
| `services/cache.py` | ✅ | Redis 우선, 실패 시 인메모리 폴백 |
| `services/entity_resolver.py` | ✅ | resolve_entity_with_profile (ProfileLoader 기반) 추가 |
| `services/profile_enricher.py` | ✅ | DART + Wikidata 자동 조회 |
| `services/profile_loader.py` | ✅ | TTL 5분 인메모리 캐시, 업종별 INDUSTRY_CONFIG |
| `services/notifier.py` | ✅ 키 있을때 / 🟡 없을때 | 임직원 우선순위 알림 강도 차등 |
| `services/report_generator.py` | ✅ | 일간/주간 위협 요약 |
| `services/data_retention.py` | ✅ | 90일 초과 데이터 자동 삭제, 서버 기동 시 실행 |

---

## 프론트엔드

| 항목 | 상태 | 비고 |
|------|------|------|
| `pages/landing.html` | ✅ | 9개 섹션 랜딩 페이지 |
| `pages/login.html` | ✅ | Google OAuth, 에러 처리 |
| `pages/dashboard.html` | ✅ | KPI, 게이지, 위협목록, 상세패널, 스캔 버튼, Mock 배너 |
| `pages/threats.html` | 🟡 | 기본 목록 있음, CSV 내보내기 미구현 |
| `pages/settings.html` | ✅ | 브랜드 프로파일 + 키워드 관리 탭 |
| `pages/reports.html` | ✅ | 일간/주간 리포트, 빈 상태 안내 포함 |
| `pages/actions.html` | ✅ | 미처리 위협 큐, 상태 변경 동작 |
| `pages/brand-image.html` | ✅ | 브랜드 건강도·모듈별 점수 실데이터 표시 |
| `pages/negative-mentions.html` | ✅ | 부정 의견 필터·상세 패널·상태 변경 동작 |
| `assets/js/dashboard.js` | ✅ | 실데이터 차트, 30초 폴링, 스캔 실행 |
| `assets/js/api.js` | ✅ | keywords, scan, trend, platform-stats API 추가 |

---

## 테스트

| 항목 | 상태 | 비고 |
|------|------|------|
| `tests/test_risk_scorer.py` | ✅ | |
| `tests/test_api.py` | ✅ | |
| `tests/test_l1_filter.py` | ✅ | |
| 전체 46/46 통과 | ✅ | `python -m pytest tests/ -v` |

---

## MVP 완료 기준 체크

| 기준 | 상태 |
|------|------|
| `uvicorn main:app --reload` 에러 없이 기동 | ✅ |
| `http://localhost:8000` 대시보드 렌더링 | ✅ |
| `/api/dashboard/threats` 정상 응답 | ✅ |
| 리스크 스코어 게이지 표시 | ✅ |
| 위협 클릭 → 상세 모달 → 상태 변경 | ✅ |
| ANTHROPIC_API_KEY 입력 시 L3 실제 동작 | ✅ (키 필요) |
| API 키 없어도 Mock으로 정상 동작 | ✅ |
| Mock 데이터임을 UI에 명시 | ✅ (Mock 배너) |
| 키워드 CRUD | ✅ |
| 리포트 페이지 | ✅ |
| Rate Limiting | ✅ |
| 이메일 알림 코드 | ✅ (SMTP 키 필요) |

---

---

## 조직 관리 + 팀 결제 시스템 (2026-05-21 추가)

| 항목 | 상태 | 비고 |
|------|------|------|
| `models/orm.py` Organization 테이블 | ✅ | slug, owner, 구독 정보 포함 |
| `models/orm.py` OrganizationMember 테이블 | ✅ | owner/admin/member/viewer 역할 |
| `models/orm.py` InviteCode 테이블 | ✅ | 8자리 코드, 만료일, 사용 횟수 |
| Threat/Keyword/CustomerProfile org_id | ✅ | nullable FK, 기존 데이터 호환 |
| `config.py` TIER_LIMITS | ✅ | free/starter/pro/enterprise |
| `services/org_service.py` | ✅ | 멤버 한도, 초대코드, 유예기간 로직 |
| `routers/orgs.py` | ✅ | CRUD, 초대코드, 승인/거절, 역할변경, 강퇴, 탈퇴 |
| `middleware/org_context.py` | ✅ | optional_current_org / get_current_org (자동 생성) |
| `routers/dashboard.py` org 필터링 | ✅ | 인증 시 org_id 기준, 미인증 시 전체 (테스트 호환) |
| `routers/billing.py` org 기반 구독 | ✅ | Polar.sh 웹훅 → org 구독 상태 갱신 |
| `workers/alert_tasks.py` 유예기간 처리 | ✅ | process_grace_periods 태스크 추가 |
| `workers/celery_app.py` beat 스케줄 | ✅ | 매일 새벽 1시 유예기간 만료 처리 |
| `db/seed.py` 기본 조직 생성 | ✅ | 시드 데이터에 org 포함 (pro 플랜) |
| `pages/join.html` 초대코드 참여 | ✅ | /orgs/join 경로 |
| `pages/org_create.html` 조직 생성 | ✅ | /orgs/new 경로 |
| `pages/dashboard.html` 조직 셀렉터 | ✅ | 사이드바 조직 전환 드롭다운 |
| `pages/settings.html` 팀 관리 섹션 | ✅ | 초대코드 발급, 멤버 승인/강퇴, 업그레이드 모달 |
| Viewer 엔드포인트 제한 | ✅ | require_non_viewer — keywords/profile/orgs write 엔드포인트 적용 |
| Org 기반 keyword/profile 필터링 | ✅ | dashboard/keywords/reports/profile 라우터 전체 적용 |

---

## 추가 구현 항목 (2026-05-26)

| 항목 | 상태 | 비고 |
|------|------|------|
| `routers/assistant.py` | ✅ | Gemini 브랜드 위기 대응 챗 (`/api/assistant/chat`) |
| `routers/webhooks.py` | ✅ | 아웃바운드 웹훅 CRUD (`/api/webhooks`) |
| `routers/competitor_keywords.py` | ✅ | 경쟁사 키워드 CRUD (`/api/competitor-keywords`) |
| `services/ai/gemini_client.py` | ✅ | 공통 Gemini 클라이언트 (캐싱·429 재시도) |
| `middleware/auth.py` require_login | ✅ | 속성 접근용 인증 의존성 — 버그 수정 (2026-05-26) |
| `services/reach_calculator.py` | ✅ | 플랫폼별 바이럴 계수 도달 범위 추정 — pipeline.py에서 사용 |
| `services/anomaly_detector.py` | ✅ | 7일 기준선 대비 급증 탐지 — `GET /api/dashboard/anomaly` 연결 |
| `services/slack_notifier.py` | ✅ | Slack Block Kit 알림 — pipeline critical·high 위협 발생 시 org.slack_webhook_url로 자동 전송 |
| `services/webhook_sender.py` | ✅ | HMAC-SHA256 서명 아웃바운드 웹훅 — pipeline critical·high 시 등록 웹훅에 자동 발송 |
| `services/influencer_detector.py` | 🟡 | 인플루언서 영향력·티어 분류 — 코드만 있음, 수집기 팔로워 데이터 없어 미통합 |

---

## 알려진 미완성 항목

1. **Instagram / TikTok 수집기** — 공식 API 접근 제한으로 미구현
2. **Celery 자동 수집** — 코드 완성, Redis 필요 (docker-compose로 로컬 실행 가능)
3. **Google OAuth** — GOOGLE_CLIENT_ID/SECRET 입력 필요 (DEMO_MODE=true로 우회 가능)
4. **Polar.sh 결제** — 실계정 설정 필요
5. **Vercel 실 배포 검증** — 로컬 기동만 검증됨
6. **⚠️ ORM 변경 시** — `brandguard.db` 삭제 후 재기동 필요 (테이블 재생성)
