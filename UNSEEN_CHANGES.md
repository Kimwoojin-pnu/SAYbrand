# SAYbrand — 미전달 변경사항 로그

> Claude.ai에서 확인하지 않은 변경사항을 여기에 누적한다.
> 동기화 시 이 파일 전체를 Claude.ai 채팅에 붙여넣는다.

마지막 동기화: 없음
────────────────────────────────────────

<!-- 새 항목은 위에서부터 추가 (최신순) -->

---
## [#42] 2026-05-26
**분류:** 실제 동작 검증 (API 키 연동 end-to-end 테스트)
**파일:**
- `PROGRESS.md` (naver 수집기 검증완료 표기)
**변경 내용 없음 — 검증 결과만 기록**

### 테스트 결과

| Step | 결과 | 비고 |
|------|------|------|
| Step 1: 서버 기동 | ✅ | `uvicorn main:app` 에러 없이 기동, `/api/dashboard/stats` 200 OK |
| Step 2: Naver 실수집 | ✅ 실제 25건 | NAVER_CLIENT_ID 키로 실제 블로그/카페/뉴스 수집 확인 |
| Step 3: Gemini L2 분석 | 🟡 MOCK | 무료 티어 할당량 초과 (429 ResourceExhausted), 코드 정상·API 한도 문제 |
| Step 4: 파이프라인 E2E | ✅ scanned:25, threats:3, is_mock:False | Naver 실데이터 기반 3건 위협 분류·DB 저장 |
| Step 5: 대시보드 | ✅ 실제 데이터 표시 | 시드 15건 + 실수집 3건 = 18건, Naver 위협 정상 표시 |

### 확인된 실제 동작 범위
- **Naver 수집기**: ✅ 실제 API 호출·콘텐츠 수집 동작
- **L1 필터**: ✅ 25건 중 3건 위협 분류 (키워드 매칭 정상)
- **DB 저장**: ✅ 파이프라인 결과 SQLite 저장 확인
- **이상 감지 API**: ✅ `detect_anomaly` 직접 실행 — is_anomaly:True, ratio:33.4 (방금 3건 급증)
- **anomaly 엔드포인트**: ✅ `/api/dashboard/anomaly` 라우팅 정상 (인증 미제공 시 401 반환 확인)

### 미동작 (키/외부 설정 필요)
- **Gemini L2**: 🟡 무료 티어 할당량 초과 → Mock 폴백 (GEMINI_API_KEY 유료 플랜 필요)
- **Claude L3**: ❌ ANTHROPIC_API_KEY 미입력 → Mock 폴백
- **google.generativeai 패키지**: ⚠️ deprecated (0.8.6), `google-genai`로 마이그레이션 필요
**Claude.ai 확인 필요:** NO
---

---
## [#41] 2026-05-26
**분류:** 통합 (미연결 서비스 파이프라인 연결)
**파일:**
- `backend/services/pipeline.py` (수정)
- `backend/routers/dashboard.py` (수정)
- `PROGRESS.md` (상태 업데이트)
**변경 내용:**
- **webhook_sender 통합**: `run_pipeline()`에서 critical·high 위협 저장 후 `_send_notifications()` 호출. 해당 user의 active OutboundWebhook을 조회해 이벤트(`threat.critical` / `threat.high`) 매칭 시 HMAC-SHA256 서명 포함 POST 전송.
- **slack_notifier 통합**: 같은 `_send_notifications()` 내에서 user가 속한 org의 `slack_webhook_url`이 설정된 경우 Slack Block Kit 포맷으로 위협 알림 발송.
- **anomaly_detector 엔드포인트**: `GET /api/dashboard/anomaly` 추가. 인증 사용자 기준 1시간 내 위협 건수 vs. 7일 평균 비교 → `is_anomaly`, `ratio` 반환.
- **PROGRESS.md**: anomaly/slack/webhook 상태 🟡→✅ 업데이트.
**Claude.ai 확인 필요:** NO
---

---
## [#40] 2026-05-26
**분류:** 버그 수정 + DB 재동기화
**파일:**
- `backend/middleware/auth.py` (수정)
- `PROGRESS.md` (상태 재검토)
**변경 내용:**
- **require_login 추가**: `assistant.py`·`webhooks.py`·`competitor_keywords.py`가 import하는 `require_login`이 `auth.py`에 없어 서버 기동 시 ImportError 발생하던 버그 수정. `LoginUser` dataclass(id/name/email) 반환.
- **brandguard.db 삭제**: ORM에 추가된 컬럼(`sentiment`, `emotion`, `sentiment_score`, `reach_estimate`, `region` 등)이 기존 DB에 없어 테스트 5개 실패. DB 삭제 후 테이블 재생성으로 46/46 복구.
- **PROGRESS.md 재검토**: actions/brand-image/negative-mentions 페이지(🟡→✅), org 필터링/Viewer 제한(🟡→✅) 상태 정정. 신규 라우터(assistant/webhooks/competitor_keywords) 항목 추가.
**Claude.ai 확인 필요:** NO
---

## [#39] 2026-05-26
**분류:** 수정 (AI 비용 최적화)
**파일:**
- `backend/services/analyzers/l2_text.py` (수정)
- `backend/services/analyzers/l3_deep.py` (수정)
- `backend/services/pipeline.py` (수정)
- `requirements.txt` (수정)
**변경 내용:**
- **L2 Gemini 모델 교체**: `gemini-1.5-flash` → `gemini-2.0-flash`. 경량 프롬프트(_GEMINI_COMPACT_PROMPT, ~100토큰) 도입. 콘텐츠 입력 500자 truncation. 응답 4필드(sentiment/threat_type/urgency/is_bot_likely)로 축소, max_output_tokens=150. 429(ResourceExhausted) 에러 → Mock 반환.
- **L2 캐시 TTL**: 3600초 → 86400초 (24시간).
- **L2 배치 처리**: `analyze_batch(posts, max_batch=10)` 추가. 최대 10건을 1 API 호출로 묶음 처리(_GEMINI_BATCH_PROMPT), JSON 배열 파싱.
- **L3 모델 교체**: Claude Haiku → Gemini 2.5 Flash(`gemini-2.5-flash-preview-05-20`) 우선, 실패 시 Claude Haiku 폴백. 경량 프롬프트(_L3_ANALYSIS_PROMPT_TEMPLATE) 도입, max_output_tokens=300. 응답 5필드(threat_assessment/is_organized_attack/legal_action_required/analysis/response_suggestion).
- **L3 캐시 추가**: TTL 43200초(12시간). 단건(`analyze`)·클러스터(`deep_analyze_cluster`) 양쪽 적용.
- **L3 호출 조건 강화**: `L3_SCORE_THRESHOLD` 0.70→0.85. `need_l3` 조건 = risk_score≥85 OR auto_critical OR (임직원언급 AND critical). 기존 `severity == "high"` 조건 제거.
- **requirements.txt**: `google-generativeai==0.8.3` → `>=0.8.3` (최신 호환 버전 허용). anthropic 유지(L3 폴백용).
**Claude.ai 확인 필요:** NO
---

## #31 — 2026-05-13: STACK_UPDATE — 고객 프로파일 데이터 전면 활용

### 신규 파일
- `services/profile_loader.py` — ProfileLoader (TTL 5분 캐시), INDUSTRY_CONFIG 6종 업종 설정

### 분석기 강화
- `analyzers/l1_filter.py` — `l1_filter_with_profile()` 추가
  - 공식 계정 화이트리스트 자동 제외
  - alias 가중치 기반 브랜드 언급 점수
  - 임직원 이름 → Module C 자동 분류
  - 사칭 계정명 패턴 탐지 (레벤슈타인·숫자 붙임)
  - 업종 민감 키워드 가중 처리
- `analyzers/l2_image.py` — `register_from_profile()`, `compare_all()` 추가 (로고+임직원사진 pHash)
- `analyzers/l3_deep.py` — `build_profile_context()` 추가 (업종·임직원·공식계정·민감키워드 컨텍스트)

### 서비스 강화
- `services/entity_resolver.py` — `resolve_entity_with_profile()` 추가 (DB 쿼리 없이 로드된 프로파일 활용)
- `services/risk_scorer.py` — `calculate_risk_score()` 업종 multiplier + 임직원 우선순위 가중치 추가, `classify_alert_threshold()` 신규
- `services/pipeline.py` — ProfileLoader 중심으로 전면 재작성 (프로파일 있으면 강화 필터, 없으면 키워드 폴백)
- `services/notifier.py` — CEO(priority=1) 언급 시 critical 강제 상향, 임원(priority=2) 언급 시 medium→high 상향

### 라우터 강화
- `routers/profile.py` — create/update/add_alias/add_executive 시 캐시 무효화 + 키워드 자동 동기화 + pHash 자동 등록

**완료 기준 검증:**
- display_name → L1 브랜드 매칭 + 수집기 키워드 ✅
- aliases → L1 가중치 + Entity Resolver + 수집기 키워드 ✅
- official_handles → L1 화이트리스트 + 사칭 탐지 ✅
- logo_url → pHash 자동 등록 ✅
- executives.name → L1 Module C + 수집기 키워드 ✅
- executives.photo_url → L2 이미지 비교 기준 ✅
- executives.priority → 리스크 가중치 + 알림 강도 ✅
- industry → 리스크 가중치 + 알림 임계값 + L1 민감어 ✅

**테스트: 46/46 통과**

## #30 — 2026-05-13: Phase 1~5 전체 구현

### Phase 1: 데이터 파이프라인
- `collectors/base.py` — RawPost dataclass + make_post(is_mock=) 추가
- `collectors/naver.py` — Mock 반환 시 is_mock=True 명시
- `collectors/x_twitter.py` — Mock 반환 시 is_mock=True 명시
- `collectors/youtube.py` [신규] — YouTube Data API v3 수집기 (키 없으면 [MOCK])
- `analyzers/l2_text.py` — is_mock 플래그 반환값에 추가
- `services/pipeline.py` [신규] — L1→L2→L3→DB 파이프라인, is_mock 전파
- `config.py` — youtube_api_key, SMTP 설정 추가
- `.env` — NAVER, X, YOUTUBE, SMTP 키 항목 추가

### Phase 2: 프론트엔드
- `assets/js/api.js` — trend, platformStats, scan(POST), keywordApi 추가
- `assets/js/dashboard.js` — 실데이터 트렌드 차트, 실데이터 플랫폼 통계, 30초 폴링, 스캔 버튼
- `pages/dashboard.html` — Mock 배너 + 스캔 버튼 추가
- `pages/reports.html` [신규] — 일간/주간 리포트 페이지 (빈 상태 안내 포함)
- `pages/settings.html` — 키워드 관리 섹션 추가 (추가/삭제/플랫폼 체크박스)

### Phase 3: 인프라
- `routers/keywords.py` [신규] — GET/POST/DELETE /api/keywords
- `routers/reports.py` [신규] — /api/reports/daily, /api/reports/weekly
- `routers/dashboard.py` — POST /api/dashboard/scan (인증 사용자), /trend, /platform-stats 추가

### Phase 4: 알림 & 리포트
- `services/notifier.py` [신규] — SMTP 이메일 알림, 키 없으면 [MOCK] 로그만
- `services/report_generator.py` [신규] — 일간/주간 위협 요약 생성

### Phase 5: 운영
- `middleware/rate_limiter.py` [신규] — 분당 60회 / 스캔 시간당 10회 제한
- `main.py` — Rate limiter, keywords, reports 라우터 등록
- `PROGRESS.md` — ✅/🟡/❌/⚠️ 기준 전면 재검토

**테스트: 46/46 통과**

---
## [#38] 2026-05-12
**분류:** 수정 (L3 분석기 고도화)
**파일:**
- `backend/services/analyzers/l3_deep.py` (수정)
- `backend/models/orm.py` (수정 — FeedbackLog 모델 추가)
**변경 내용:**
- **개선 1 — 클러스터 분석**: `deep_analyze_cluster(threats, profile_id, db)` 추가. 연관 위협 최대 10건을 1 API 호출로 분석. `_CLUSTER_SYSTEM_PROMPT` 별도 정의 (JSON 출력 강제). max_tokens=800 (단건 1024 대비 절감). 단건 10회 대비 입력 토큰 ~60% 절약.
- **개선 2 — 계정 히스토리 주입**: `analyze()`에 `source_account` 파라미터 추가. `_build_account_history()` — 동일 계정 과거 위협 3건 조회 → 프롬프트 주입. "이 계정의 과거 위협 기록: N건" 형식.
- **개선 3 — 오탐 피드백**: `record_feedback(threat_id, original_verdict, actual_verdict, marked_by, db)` 추가. `FeedbackLog` 테이블 저장. `_extract_json()` 헬퍼로 마크다운 코드 블록 포함 JSON 안전 파싱.
- **DB 재시딩 필요**: `brandguard.db` 삭제 후 서버 재기동 (feedback_logs 테이블 추가).
**Claude.ai 확인 필요:** NO
---

---
## [#37] 2026-05-12
**분류:** 신규 (데이터 수집기 1단계 + scan 엔드포인트)
**파일:**
- `backend/services/collectors/base.py` (신규)
- `backend/services/collectors/naver.py` (신규)
- `backend/services/collectors/x_twitter.py` (신규)
- `backend/config.py` (수정 — naver_client_id, naver_client_secret, x_bearer_token 추가)
- `backend/routers/dashboard.py` (수정 — GET /api/dashboard/scan 추가)
**변경 내용:**
- **base.py**: `BaseCollector` 추상 클래스 + `make_post()` 반환 형식 통일 헬퍼.
- **naver.py**: 블로그/카페/뉴스 병합 수집 (display 분배: 50%/33%/17%). HTML 엔티티 제거, postdate(YYYYMMDD)·pubDate(RFC822) 파싱. API 키 없으면 Mock 3건 반환.
- **x_twitter.py**: API v2 `tweets/search/recent`. author 확장으로 팔로워 수·계정생성일 포함. 429 한도 초과·오류 시 Mock 2건 반환.
- **GET /api/dashboard/scan**: `keyword` + `platforms`(naver|x|all) 파라미터. 수집→L1 필터→Threat DB 저장→결과 요약 반환.
- **.env 추가 키**: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `X_BEARER_TOKEN`
**Claude.ai 확인 필요:** NO
---

---
## [#36] 2026-05-12
**분류:** 신규 (L2 분석기 + 캐시 + 비용 추적)
**파일:**
- `backend/services/cache.py` (신규)
- `backend/services/analyzers/l2_text.py` (신규)
- `backend/services/analyzers/l2_image.py` (신규)
- `backend/services/analyzers/l2_cost_tracker.py` (신규)
- `backend/models/orm.py` (수정 — UsageLog 모델 추가)
- `backend/config.py` (수정 — hyperclova_api_key, hyperclova_gateway_key 추가)
- `requirements.txt` (수정 — redis>=5.0.0 추가)
**변경 내용:**
- **cache.py**: Redis 우선 연결, 실패 시 인메모리 폴백. `get/set/setex` 래퍼. 연결 오류는 경고 로그만 출력 (에러 없음).
- **l2_text.py**: `KR_SNS_ANALYSIS_PROMPT` (반어법·줄임말·커뮤니티어·봇패턴 반영), `call_l2_with_fallback()` HyperCLOVA→Gemini→Mock 순 폴백, `analyze_text_with_cache()` TTL 1시간 캐싱. `_meta` 필드에 모델명·토큰수 포함.
- **l2_image.py**: `LogoSimilarityEngine` 클래스. `register_logo()` pHash 등록, `compare()` 해밍 거리 ≤10 → `is_suspicious=True`. URL 직접 등록·비교 지원. 실패 시 안전 기본값 반환.
- **l2_cost_tracker.py**: `record_usage()` — 모델·레이어·토큰·비용 기록. `get_usage_summary()` — 유저별 누적 비용 집계.
- **orm.py**: `UsageLog` 테이블 추가 (user_id, profile_id, model, layer, tokens_in, tokens_out, cost_usd).
- **DB 재시딩 필요**: `brandguard.db` 삭제 후 서버 재기동.
**Claude.ai 확인 필요:** NO
---

---
## [#35] 2026-05-12
**분류:** 신규 (L1 필터 + 키워드 데이터베이스)
**파일:**
- `backend/services/analyzers/keyword_database.py` (신규 — 루트 `keyword_database.py`에서 이동)
- `backend/services/analyzers/l1_filter.py` (신규)
- `tests/test_l1_filter.py` (신규)
**변경 내용:**
- **keyword_database.py 이동**: 루트에 있던 파일을 `backend/services/analyzers/`로 이동. `KEYWORD_DATABASE` / `NEGATIVE_KEYWORD_LIST` / `CRITICAL_BYPASS` export.
- **l1_filter.py 재작성**: 기존 하드코딩 `THREAT_KEYWORDS` 제거. `KEYWORD_DATABASE` 기반 카테고리 스캔으로 교체.
  - `requires_brand=True` 카테고리: `brand_keywords` 인자에 브랜드명이 텍스트에 있을 때만 스코어
  - `NEGATIVE_KEYWORD_LIST` 히트 시 총점 40% 감소 (`raw_score *= 0.60`)
  - `CRITICAL_BYPASS` 키워드 히트 시 즉시 `auto_critical=True`, `score=1.0` 반환
  - 반환값에 `score(0.0~1.0)` 추가 (기존 pass/fail 확장)
  - 심각도: critical(≥0.70) / high(≥0.45) / medium(≥0.25) / low(≥0.10)
- **test_l1_filter.py**: CRITICAL_BYPASS, requires_brand, 음성 필터, 점수 누적, 심각도 임계값 케이스 포함
**Claude.ai 확인 필요:** NO
---

---
## [#34] 2026-05-11
**분류:** 수정 (로고 정렬 + 다크모드 기본값)
**파일:**
- `frontend/assets/css/landing.css` (수정)
- `frontend/pages/landing.html` (수정)
- `frontend/pages/dashboard.html` (수정)
**변경 내용:**
- **방법 B 로고 처리**: `saybrand-logo.png`에 텍스트 포함이므로 이미지 단독 표시. nav/footer/dashboard 모두에서 텍스트 span을 `display:none` fallback으로 전환. 이미지 로드 실패 시에만 텍스트 표시.
- **nav 로고 CSS**: `display:block; flex-shrink:0; line-height:1` 추가 → inline 기본값의 하단 여백 제거, 수직 중앙 정렬 보정. 높이 45px→40px.
- **footer 로고 CSS**: `display:block` 추가.
- **다크모드 nav 로고**: `[data-theme="dark"] .ld-nav-logo-img { filter:brightness(0) invert(1); opacity:.85; }` — 다크 네비에서 흰색 로고로 표시.
- **dashboard 사이드바**: SVG 플레이스홀더 + 텍스트 → PNG 로고(`filter:brightness(0) invert(1)`)로 교체. 다크 사이드바에서 흰색 로고 표시.
- **다크모드 기본값**: `<head>` 인라인 스크립트에서 `localStorage` 미설정 시 기본 `'dark'` 적용.
**Claude.ai 확인 필요:** NO
---

---
## [#33] 2026-05-11
**분류:** 수정 (다크모드 + 로고 크기)
**파일:** `frontend/assets/css/landing.css`, `frontend/pages/landing.html`
**변경 내용:**
- 다크모드 토글 버튼(달/해 아이콘) nav 추가. `[data-theme="dark"]` CSS 변수 오버라이드 + 요소별 재정의(nav, card, pricing, pipeline, footer 등). `localStorage` 저장으로 선택 유지. `<head>` 인라인 스크립트로 FOUC 방지. 기본값 dark.
- nav 로고 30px→45px, footer 로고 28px→42px.
**Claude.ai 확인 필요:** NO
---

---
## [#32] 2026-05-11
**분류:** 수정 (랜딩 히어로 임팩트 강화 + 마이크로 인터랙션)
**파일:**
- `frontend/assets/css/landing.css` (수정)
- `frontend/pages/landing.html` (수정)
**변경 내용:**
- **히어로 오버레이 카드 2개 교체:** 기존 float-card 대신 `.mock-score-card`(좌상단, 다크, 브랜드 위협 지수 카운트업) + `.mock-alert-card`(우하단, 화이트, CRITICAL 뱃지 + 펄스 도트)로 교체. 각각 0.8s / 1.2s 딜레이 spring 애니메이션 진입.
- **히어로 배경 글로우:** `.ld-hero::after` — brand-blue 7% opacity 600px radial gradient 우상단 배치.
- **KPI 카운트업:** 스탯 바 4개 수치(12,400+ / 9.2M / 47초 / NPS 67) — Intersection Observer 뷰포트 진입 시 1회 easeOutCubic 1.5초 카운트업.
- **히어로 스코어 카운트업:** 페이지 로드 1초 후 `#hero-score` 0→73 카운트업.
- **섹션 스크롤 진입 애니메이션:** 섹션 ③④⑤⑥⑦⑧에 `.animate-section` 클래스 추가 — 뷰포트 15% 진입 시 opacity+translateY(20px→0) fade-slide, 1회 실행.
- **버튼 hover 부상:** `.ld-btn--dark:hover` / `.ld-btn--outlined:hover` — `translateY(-1px)` + `:active` 복귀.
- **네비 링크 언더라인 슬라이드:** `.ld-nav-links a::after` — width 0→100% 0.2s ease.
- **피처 카드 hover:** `.feature-card` 클래스 — `.ld-threat-card-demo`, `.bot-network-wrap`에 적용. 테두리 브라이트업 + translateY(-2px).
- **가격 카드 hover:** `.ld-plan-card:hover` translateY(-4px). Pro 카드 기본 -4px 부상, hover -8px.
- **CTA shimmer:** `.ld-plan-cta--primary::before` — 60% 너비 흰색 8% shimmer 3초 반복.
- **네비 스크롤:** scrollY > 40px 시 frosted glass 전환 (기존 > 20px에서 변경).
**Claude.ai 확인 필요:** NO
---

---
## [#31] 2026-05-09
**분류:** 신규생성 + 수정 (랜딩 페이지 + 라우팅 재편)
**파일:**
- `frontend/pages/landing.html` (신규) — 기업 홈페이지 수준 랜딩 페이지 (9개 섹션)
- `frontend/assets/css/landing.css` (신규) — 랜딩 전용 CSS (NanumSquare 폰트, 디자인 시스템 토큰)
- `main.py` (수정) — `/` → landing.html (인증불필요), `/dashboard` 신규 보호 라우트 추가, `/saybrand-logo.png` 로고 서빙 라우트
- `backend/routers/auth.py` (수정) — OAuth callback + demo-login 리다이렉트를 `/` → `/dashboard`로 변경
- `frontend/pages/login.html` (수정) — "← 홈으로" 링크 추가
- `frontend/pages/dashboard.html` (수정) — 사이드바 로고 클릭 시 `target="_blank"`로 `/` 열기, nav 대시보드 링크를 `/dashboard`로 변경
**변경 내용:**
- `/` 경로가 로그인 필요 대시보드에서 퍼블릭 랜딩 페이지로 전환됨
- 랜딩: 탑 네비 / 히어로(대시보드 목업) / 스탯 바(4 KPI) / 피처A(모듈 A 사칭탐지) / 피처B(모듈 B 봇네트워크 SVG) / 다크 AI 파이프라인 / 가격(3플랜) / CTA / 푸터(4컬럼)
- NanumSquare CDN 연동 (300/400/700/800 웨이트), 모든 헤딩 네거티브 레터스페이싱 적용
- 반응형: 1280px / 768px / 480px 3 브레이크포인트
**Claude.ai 확인 필요:** NO
---

---
## [#30] 2026-05-08
**분류:** 수정 (서비스명 변경)
**파일:** `.env`, `backend/config.py`, `main.py`, `frontend/pages/dashboard.html`, `frontend/pages/login.html`, `frontend/pages/settings.html`, `backend/db/seed.py`, `CLAUDE.md`, `CHECKLIST.md`, `README.md`, `PRD.md`, `TRD.md`, `STACK_UPDATE.md`, `SNAPSHOT.md`, `PROGRESS.md`, `UNSEEN_CHANGES.md`
**변경 내용:** 서비스 가칭을 SAYbrand로 확정. 코드·문서·UI 텍스트 전반의 "BrandGuard AI" / "BrandGuard" 표기를 SAYbrand로 일괄 변경. 파일명·디렉토리명(brandguard.db 등)은 유지.
**Claude.ai 확인 필요:** NO
---

---
## [#29] 2026-05-07
**분류:** 수정
**파일:** `.env`
**변경 내용:** `DART_API_KEY=` 항목 추가 (https://opendart.fss.or.kr 무료 발급).
**Claude.ai 확인 필요:** NO
---

---
## [#28] 2026-05-07
**분류:** 수정
**파일:** `main.py`
**변경 내용:** `profile` 라우터 등록, `GET /settings` 라우트 추가 (미인증 시 /login 리다이렉트).
**Claude.ai 확인 필요:** NO
---

---
## [#27] 2026-05-07
**분류:** 수정
**파일:** `backend/config.py`
**변경 내용:** `dart_api_key: str = ""` 설정 항목 추가.
**Claude.ai 확인 필요:** NO
---

---
## [#26] 2026-05-07
**분류:** 신규생성
**파일:** `frontend/pages/settings.html`
**변경 내용:** 고객 프로파일 온보딩 UI. 탭 4개 (기본정보·이름변형·공식계정·임직원). DART 자동조회 버튼, alias 중요도 슬라이더, 공식 계정 등록, 임직원 우선순위 선택 포함. 전체 CRUD JS로 구현.
**Claude.ai 확인 필요:** NO
---

---
## [#25] 2026-05-07
**분류:** 신규생성
**파일:** `backend/routers/profile.py`
**변경 내용:** `/api/profile` CRUD (생성·조회·수정) + aliases·social-accounts·executives 서브리소스 CRUD + `/enrich/dart`·`/enrich/wikidata` 엔리치먼트 엔드포인트. 모두 get_current_user 보호.
**Claude.ai 확인 필요:** NO
---

---
## [#24] 2026-05-07
**분류:** 신규생성
**파일:** `backend/services/analyzers/l3_deep.py`
**변경 내용:** Claude Haiku 4.5 호출로 위협 심층 분석. 고객 프로파일(display_name·aliases·공식계정·업종)을 시스템 프롬프트에 주입. ANTHROPIC_API_KEY 없으면 Mock fallback 자동 적용.
**Claude.ai 확인 필요:** NO
---

---
## [#23] 2026-05-07
**분류:** 신규생성
**파일:** `backend/services/entity_resolver.py`
**변경 내용:** `resolve_entity()` — alias 가중치 합산으로 relevance_score 0~1 산출. 공식 계정과 일치하면 score=0(오탐 제외). 0.5 이상이면 is_relevant=True, confidence high/medium/low 분류.
**Claude.ai 확인 필요:** NO
---

---
## [#22] 2026-05-07
**분류:** 신규생성
**파일:** `backend/services/profile_enricher.py`
**변경 내용:** `enrich_from_dart(corp_code)` — DART API로 회사명·대표자·업종·설립일·홈페이지 조회. `search_wikidata(company_name)` — QID 검색 후 P18(로고)·P2003(Instagram)·P2002(X)·P2397(YouTube) 속성 추출. API 키 없거나 실패 시 None 반환(graceful).
**Claude.ai 확인 필요:** NO
---

---
## [#21] 2026-05-07
**분류:** 수정
**파일:** `backend/services/risk_scorer.py`
**변경 내용:** `recency_weight(detected_at)` 추가 — 1시간 내 1.0, 7일+ 0.1로 감쇠. `velocity_bonus(engagements_per_hour)` 추가 — 최대 +0.3. `calculate_risk_score()`에 두 함수 적용: `final = base * (recency + velocity)`, 0~100 클리핑. 기존 파라미터 모두 하위호환 유지(default값).
**Claude.ai 확인 필요:** NO
---

---
## [#20] 2026-05-07
**분류:** 수정
**파일:** `backend/models/schemas.py`
**변경 내용:** ThreatBase에 post_published_at·engagements_per_hour 추가. CustomerProfileCreate·CustomerProfileOut·CustomerAliasCreate/Out·CustomerSocialAccountCreate/Out·CustomerExecutiveCreate/Out·DartLookupResult·WikidataLookupResult·EntityResolverResult 스키마 추가.
**Claude.ai 확인 필요:** NO
---

---
## [#19] 2026-05-07
**분류:** 수정
**파일:** `backend/models/orm.py`
**변경 내용:** Threat에 `post_published_at(nullable DateTime)`, `engagements_per_hour(Float, default=0.0)` 추가. 신규 테이블 4개: CustomerProfile·CustomerAlias·CustomerSocialAccount·CustomerExecutive.
**Claude.ai 확인 필요:** NO
---

---
## [#18] 2026-05-07
**분류:** 신규생성
**파일:** `SNAPSHOT.md`
**변경 내용:** Claude.ai 동기화용 100줄 이내 스냅샷. 파일목록·.env 키·DB 스키마·에러·최근수정 포함.
**Claude.ai 확인 필요:** NO
---

---
## [#17] 2026-05-07
**분류:** 신규생성
**파일:** `PROGRESS.md`
**변경 내용:** 완료 파일 28개·미완료 15개·현재 실행 상태·다음 작업 전체 정리.
**Claude.ai 확인 필요:** NO
---

---
## [#16] 2026-05-07
**분류:** 신규생성
**파일:** `CHECKLIST.md`
**변경 내용:** Google OAuth 등록 → .env 입력 → 로컬 확인 → GitHub → Vercel 배포 6단계 체크리스트.
**Claude.ai 확인 필요:** NO
---

---
## [#15] 2026-05-07
**분류:** 신규생성
**파일:** `.gitignore`
**변경 내용:** .env / *.db / __pycache__ / venv / .vercel 등 GitHub 업로드 제외 목록 생성.
**Claude.ai 확인 필요:** NO
---

---
## [#14] 2026-05-07
**분류:** 수정
**파일:** `.env.example`
**변경 내용:** GOOGLE_CLIENT_ID·SECRET·REDIRECT_URI·SESSION_SECRET_KEY·POLAR_* 키 항목 추가.
**Claude.ai 확인 필요:** NO
---

---
## [#13] 2026-05-07
**분류:** 신규생성
**파일:** `README.md`
**변경 내용:** 로컬 실행법·Google OAuth 앱 등록·Vercel 배포 체크리스트·SQLite 주의사항 작성.
**Claude.ai 확인 필요:** NO
---

---
## [#12] 2026-05-07
**분류:** 수정
**파일:** `.env`
**변경 내용:** GOOGLE_CLIENT_ID·GOOGLE_CLIENT_SECRET·GOOGLE_REDIRECT_URI·SESSION_SECRET_KEY·POLAR_ACCESS_TOKEN·POLAR_WEBHOOK_SECRET·POLAR_PRODUCT_ID 키 항목 추가 (값은 비워둠).
**Claude.ai 확인 필요:** NO
---

---
## [#11] 2026-05-07
**분류:** 신규생성
**파일:** `vercel.json`
**변경 내용:** @vercel/python 빌드, 전체 라우트를 main.py로 라우팅하는 serverless 설정.
**Claude.ai 확인 필요:** NO
---

---
## [#10] 2026-05-07
**분류:** 수정
**파일:** `requirements.txt`
**변경 내용:** authlib==1.3.2 / itsdangerous==2.2.0 / polar-sdk 추가.
**Claude.ai 확인 필요:** NO
---

---
## [#9] 2026-05-07
**분류:** 수정
**파일:** `main.py`
**변경 내용:** SessionMiddleware 추가, auth·billing 라우터 등록, GET /login 라우트 추가, GET /는 세션 없으면 /login으로 리다이렉트.
**Claude.ai 확인 필요:** NO
---

---
## [#8] 2026-05-07
**분류:** 수정
**파일:** `frontend/pages/dashboard.html`
**변경 내용:** 사이드바 하단 유저 섹션 동적화(아바타·이름·이메일), 로그아웃 버튼 추가, /auth/me 호출로 미인증 시 /login 자동 리다이렉트 스크립트 추가.
**Claude.ai 확인 필요:** NO
---

---
## [#7] 2026-05-07
**분류:** 신규생성
**파일:** `frontend/pages/login.html`
**변경 내용:** "Google로 시작하기" 버튼 1개. 기존 대시보드 디자인 통일, 에러 파라미터 파싱해 오류 메시지 표시.
**Claude.ai 확인 필요:** NO
---

---
## [#6] 2026-05-07
**분류:** 신규생성
**파일:** `backend/middleware/auth.py`
**변경 내용:** get_current_user 의존성 함수. request.session에서 user_id 확인, 없으면 HTTP 401 반환.
**Claude.ai 확인 필요:** NO
---

---
## [#5] 2026-05-07
**분류:** 신규생성
**파일:** `backend/routers/billing.py`
**변경 내용:** GET /billing/checkout — Polar.sh REST API 호출로 결제 URL 생성 후 리다이렉트. POST /billing/webhook — Standard Webhooks HMAC-SHA256 서명 검증 후 구독 이벤트 처리.
**Claude.ai 확인 필요:** YES
**이유:** polar-sdk 대신 httpx로 직접 REST 호출 구현. Polar.sh 실제 checkout 엔드포인트(/v1/checkouts/)와 응답 필드명(url) 프로덕션 테스트 필요.
---

---
## [#4] 2026-05-07
**분류:** 신규생성
**파일:** `backend/routers/auth.py`
**변경 내용:** GET /auth/login·callback·logout·me — Google OAuth 2.0 + 세션 저장(user_id·name·email·avatar·subscription_status). users 테이블 upsert.
**Claude.ai 확인 필요:** NO
---

---
## [#3] 2026-05-07
**분류:** 수정
**파일:** `backend/models/schemas.py`
**변경 내용:** UserOut 스키마, SubscriptionStatus Literal 추가.
**Claude.ai 확인 필요:** NO
---

---
## [#2] 2026-05-07
**분류:** 수정
**파일:** `backend/models/orm.py`
**변경 내용:** User 모델에 google_id·avatar_url·polar_customer_id·subscription_status·subscription_tier 추가.
**Claude.ai 확인 필요:** NO
---

---
## [#1] 2026-05-07 (이전 완료)
**분류:** 신규생성
**파일:** `frontend/assets/css/custom.css`
**변경 내용:** Syne·Noto Sans KR·JetBrains Mono 폰트 정의, severity 색상 토큰, 게이지 애니메이션, 슬라이드오버 트랜지션.
**Claude.ai 확인 필요:** NO
---
