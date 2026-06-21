# SAYbrand — 프로젝트 종합 문서

> **용도:** 발표용 PPT 제작 · 데모 영상 촬영 · Claude Code 컨텍스트 참조  
> **버전:** v0.3.1 (2026-06-20 기준)  
> **작성:** 자동 생성 (코드베이스 전수 분석)

---

## 1. 제품 정의

### 한 줄 정의
**SAYbrand**는 공개 SNS 데이터를 AI로 실시간 분석하여 브랜드를 위협하는 모든 요소를 사전 탐지·대응하는 **B2B 브랜드 보호 SaaS**입니다.

### 핵심 가치
| 가치 | 설명 |
|---|---|
| 24시간 자동 감시 | 브랜드 사칭·가짜뉴스·루머·임직원 리스크를 사람 없이 탐지 |
| AI 위협 판단 | 즉각 알림 vs 정기 리포트를 AI가 자동 분기 |
| 조직적 공격 구분 | 봇 공격과 실제 소비자 불만을 분리해 불필요한 법적 대응 방지 |

### 타겟 고객
- **B2C 브랜드** (뷰티·패션·식품): 사칭 계정, 바이럴 루머 대응
- **브랜드 모니터링 체계가 없는 중견기업**: 첫 모니터링 솔루션
- **팔로워 1만+ 개인 인플루언서**: 본인 사칭 계정, 악의적 루머

---

## 2. 기술 스택

```
Backend:   FastAPI 0.115 + SQLAlchemy 2.0 async (Python 3.11+)
Frontend:  Tailwind CSS (CDN) + Vanilla JS (빌드 없음)
Database:  SQLite (로컬) / PostgreSQL (Railway 운영)
Cache:     Redis + Celery 5.4
AI L2:     Gemini 2.5 Flash Lite (google-genai ≥ 1.0.0)
AI L3:     Claude Haiku 4.5 (anthropic ≥ 0.50.0)
이미지:    imagehash 4.3.2 (pHash)
보고서:    ReportLab ≥ 4.0, python-pptx ≥ 0.6.21
배포:      Vercel (API + 프론트) + Railway (Celery 워커)
인증:      Google OAuth 2.0 (Authlib)
결제:      Polar (체크아웃 링크 방식, Svix 웹훅)
알림:      Slack Webhook (slack-sdk ≥ 3.27.0)
```

---

## 3. 시스템 아키텍처

### 3.1 전체 흐름

```
[SNS 플랫폼]
    │ YouTube API · Naver Search API · X Bearer Token
    ▼
[수집기 Orchestrator]
    │ 30분 주기 Celery Beat 스케줄
    ▼
[L1 규칙 기반 필터] ──── 탈락(score < 0.05) ──→ 버림
    │ 통과
    ▼
[Entity Resolver] ← 브랜드 프로파일 / 공식 계정 목록
    │
    ▼
[L2 텍스트 분석] ← HyperCLOVA X → Gemini 2.5 Flash Lite → KNU 감성 사전
    │ 고위협(score ≥ 0.85)
    ▼
[L3 심층 분석] ← Gemini 2.5 Flash Lite → Claude Haiku 4.5 (폴백)
    │
    ▼
[리스크 스코어링 엔진] → risk_score 0–100 산출
    │
    ▼
[DB 저장] → PostgreSQL / SQLite
    │
    ├─→ [대시보드 API] → 프론트엔드 실시간 표시
    ├─→ [Slack / 이메일 알림] ← 위협 등급별 분기
    └─→ [PDF / PPT 보고서] ← 일간·주간·월간
```

### 3.2 3계층 AI 파이프라인 (핵심 설계)

```
L1 — 규칙 기반 필터 ($0)
  ├ 900개+ 키워드 데이터베이스 (18개 카테고리)
  ├ CRITICAL_BYPASS 즉시 통과 (법적 위협 패턴 등)
  ├ NEGATIVE_FILTERS 20개+ (오탐 방지: 범용어 제거)
  └ score 0.05 미만 → 탈락 (비용 발생 없음)

L2 — AI 감성·의도 분석 (저비용)
  ├ HyperCLOVA X (기본) → Gemini 2.5 Flash Lite (폴백) → KNU 사전 (최종 폴백)
  ├ 12개 마케팅 위기 카테고리 분류
  ├ 감성(positive/neutral/negative) + 감정(분노/공포/혐오 등)
  ├ 봇 확률(0.0–1.0) + 조직적 공격 여부 판별
  └ 배치 처리 (10건/호출)로 비용 최소화

L3 — 심층 대응 분석 (고비용, 선택적)
  ├ risk_score ≥ 85 인 고위협 케이스만 호출
  ├ Gemini 2.5 Flash Lite (기본) → Claude Haiku 4.5 (폴백)
  ├ brand_damage_type 분류 (매출타격·채용악영향·파트너십위험 등)
  ├ communication_urgency (즉시 1시간내 / 당일 24시간 / 48시간내 / 모니터링)
  └ response_suggestion: SNS 대응·공식 채널 대응·내부 조치 3가지 구체 제안
```

---

## 4. 리스크 스코어링 엔진

### 4.1 위협 점수 계산 공식

```python
base = SEVERITY_WEIGHTS[severity] × MODULE_WEIGHTS[module] × PLATFORM_WEIGHTS[platform] × confidence × 100

# 업종별 가중치 적용
base *= industry_config["risk_multiplier"]

# 임직원 우선순위 (Module C)
exec_multiplier = {1: 1.5, 2: 1.2, 3: 1.0}[executive_priority]

# 조직적 공격 30% 가산
if is_organized: base = min(base * 1.3, 100)

# 최신성 가중치 (recency) × 확산 속도 보너스 (velocity)
final = base × (recency_weight + velocity_bonus)
risk_score = clamp(round(final), 0, 100)
```

### 4.2 가중치 테이블

| 구분 | 항목 | 가중치 |
|---|---|---|
| 심각도 | critical / high / medium / low | 1.0 / 0.7 / 0.4 / 0.15 |
| 모듈 | A(사칭) / B(루머) / C(임직원) | 1.0 / 0.85 / 0.7 |
| 플랫폼 | Instagram / YouTube / TikTok / X / Naver | 1.0 / 0.9 / 0.85 / 0.8 / 0.7 |

### 4.3 최신성 가중치 (recency_weight)

| 경과 시간 | 가중치 |
|---|---|
| < 1시간 | 1.0 |
| 1–6시간 | 0.9 |
| 6–24시간 | 0.75 |
| 1–3일 | 0.5 |
| 3–7일 | 0.3 |
| 7일 초과 | 0.1 |

### 4.4 전체 브랜드 점수

```
Overall = Module_A × 0.40 + Module_B × 0.35 + Module_C × 0.25

임계값:
  80–100 → CRITICAL  (즉각 Slack 알림)
  60–79  → HIGH      (당일 대응)
  35–59  → MEDIUM    (모니터링)
  0–34   → LOW       (정기 리포트)
```

### 4.5 조직적 공격 탐지 알고리즘

6가지 컴포넌트의 가중합으로 `attack_score` (0.0–1.0) 산출:

| 컴포넌트 | 의미 | 가중치 |
|---|---|---|
| text_uniformity | 텍스트 동일성 (1 - 분산) | 0.25 |
| account_cluster | 공격 계정 간 맞팔 비율 | 0.20 |
| account_quality_inverse | 계정 품질 낮을수록 ↑ | 0.20 |
| temporal_cluster | 게시 시각 집중도 (60분 기준) | 0.15 |
| cross_platform | 플랫폼 간 시간 차이 < 1시간 | 0.10 |
| reaction_uniformity | 반응 다양성 낮을수록 ↑ | 0.10 |

- `attack_score ≥ 0.7` → **organized_attack** (조직적 공격)
- `attack_score 0.4–0.7` → **gray_zone** (회색지대)
- `attack_score < 0.4` → **legitimate_criticism** (정당한 비판)

---

## 5. 데이터 수집기

### 5.1 플랫폼별 구현 상태

| 플랫폼 | 상태 | API | 비고 |
|---|---|---|---|
| Naver 블로그·카페·뉴스 | ✅ 실동작 | NAVER_CLIENT_ID/SECRET | 검증 완료 |
| YouTube 댓글 | ✅ 키 있을 때 | YOUTUBE_API_KEY | remove_pii 적용 |
| X (Twitter) | ✅ 키 있을 때 | X_BEARER_TOKEN | remove_pii 적용 |
| 한국 커뮤니티 | 🟡 Mock | 크롤링 (robots.txt 준수) | 에펨·더쿠·클리앙 등 |
| Instagram | ❌ 미구현 | Meta API 접근 제한 | v1.1 목표 |
| TikTok | ❌ 미구현 | API 접근 제한 | v1.1 목표 |

### 5.2 컴플라이언스

- **robots.txt 자동 체크**: 수집 전 허용 여부 확인
- **PII 마스킹**: 전화번호·이메일·주민번호 정규식 비식별화
- **Rate Limiter**: 요청 간 최소 2초 지연
- **뉴스 도메인 분류**: `is_news_domain()` 함수로 언론사 구분

---

## 6. 데이터베이스 스키마

### 주요 테이블 (SQLAlchemy ORM)

#### `threats` — 위협 정보
```
id, user_id, org_id, module(A/B/C), threat_type, severity
platform, source_account, source_url, content_preview
confidence, risk_score, ai_analysis, ai_response_suggestion
bot_probability, is_organized, sentiment, emotion, sentiment_score
reach_estimate, status, resolution_type, resolution_method, resolution_note
detected_at, updated_at
```

#### `users` — 사용자
```
id, name, email, company, user_type(google)
google_id, avatar_url, polar_customer_id
subscription_status(free/active/canceled), subscription_tier
created_at
```

#### `organizations` — 조직 (다중 사용자)
```
id, name, slug, owner_user_id
invite_mode(approval/open), subscription_tier, subscription_status
slack_webhook_url, white_label_enabled, white_label_logo/brand_name/color
```

#### `organization_members` — 조직 멤버십
```
id, org_id, user_id, role(owner/admin/member/viewer)
status(pending/active), joined_at
```

#### `customer_profiles` — 브랜드 프로파일
```
id, user_id, org_id, profile_type(company/individual)
display_name, industry, description, logo_url
dart_corp_code, wikidata_id
```

#### `customer_aliases` — 브랜드 별칭
```
id, profile_id, alias, alias_type(official/nickname/abbreviation/english)
weight (1.0 기본)
```

#### `customer_executives` — 임직원 (Module C)
```
id, profile_id, name, role(CEO/CFO/임원/...)
photo_url, priority(1=CEO / 2=임원 / 3=일반)
```

#### `keywords` — 모니터링 키워드
```
id, user_id, org_id, keyword, platforms(JSON), active
```

#### `invite_codes` — 초대 코드
```
id, org_id, code(20자), role_to_assign, expires_at, max_uses, uses_count
```

#### `usage_logs` — AI API 사용량 추적
```
id, user_id, profile_id, model, layer(L2_text/L2_image/L3)
tokens_in, tokens_out, cost_usd
```

#### `archived_threats` — 조치 완료 보관함
```
id, original_threat_id, severity, threat_type, platform
action_taken, resolution_note, archived_at, expires_at(90일)
```

---

## 7. API 엔드포인트

### 7.1 대시보드 (`/api/dashboard`)
| 엔드포인트 | 메서드 | 설명 |
|---|---|---|
| `/api/dashboard/threats` | GET | 위협 목록 (필터·정렬·페이지) |
| `/api/dashboard/threats/{id}` | GET | 위협 상세 |
| `/api/dashboard/threats/{id}` | PATCH | 위협 상태 변경 |
| `/api/dashboard/scan` | POST | 스캔 실행 (Vercel→Celery / 로컬→직접) |
| `/api/dashboard/scan-local` | POST | 로컬 전용 직접 스캔 |
| `/api/dashboard/stats` | GET | 통계 (severity별·platform별 집계) |
| `/api/dashboard/version` | GET | 서비스 버전 반환 |

### 7.2 보고서 (`/api/reports`)
| 엔드포인트 | 메서드 | 설명 |
|---|---|---|
| `/api/reports/{period}` | GET | JSON 리포트 (daily/weekly/monthly) |
| `/api/reports/{period}/pdf` | GET | PDF 보고서 다운로드 |
| `/api/reports/{period}/pptx` | GET | PPT 보고서 다운로드 (6슬라이드) |
| `/api/reports/threat-map` | GET | 플랫폼별 위협 인텔리전스 맵 |
| `/api/reports/archives` | GET | 조치 완료 아카이브 |

### 7.3 인증 (`/auth`)
| 엔드포인트 | 메서드 | 설명 |
|---|---|---|
| `/auth/google` | GET | Google OAuth 시작 |
| `/auth/callback` | GET | OAuth 콜백, JWT 발급 |
| `/auth/logout` | GET | 세션 종료 |
| `/auth/me` | GET | 현재 사용자 정보 |

### 7.4 조직 (`/api/orgs`)
| 엔드포인트 | 메서드 | 설명 |
|---|---|---|
| `/api/orgs` | POST | 조직 생성 |
| `/api/orgs/{id}/join` | POST | 초대코드로 참여 |
| `/api/orgs/{id}/members` | GET | 멤버 목록 |
| `/api/orgs/{id}/members/{uid}` | PATCH | 멤버 역할·상태 변경 |
| `/api/orgs/{id}/invite-codes` | GET | 초대 코드 조회 |
| `/api/orgs/{id}/pending` | GET | 승인 대기 목록 |

### 7.5 결제 (`/billing`)
| 엔드포인트 | 메서드 | 설명 |
|---|---|---|
| `/billing/checkout/{plan}` | GET | Polar 체크아웃 링크 리다이렉트 |
| `/billing/webhook` | POST | Polar Svix 웹훅 (Svix 서명 검증) |
| `/billing/sync` | POST | 이메일 기준 구독 수동 동기화 |

### 7.6 기타
| 엔드포인트 | 메서드 | 설명 |
|---|---|---|
| `/api/keywords` | GET/POST/DELETE | 모니터링 키워드 관리 |
| `/api/profile` | GET/POST/PATCH | 브랜드 프로파일 CRUD |
| `/api/support` | GET/POST | 고객센터 티켓 |
| `/api/assistant/chat` | POST | AI 어시스턴트 채팅 |
| `/api/activity` | GET | 활동 로그 |

---

## 8. 프론트엔드 페이지

### 8.1 퍼블릭 페이지
| URL | 파일 | 설명 |
|---|---|---|
| `/` | `landing.html` | 마케팅 랜딩 페이지 |
| `/products` | `products/index.html` | 5개 기능 탭 통합 소개 |
| `/login` | `login.html` | Google OAuth 로그인 |
| `/onboarding` | `onboarding.html` | 3단계 온보딩 (경로선택→조직설정→브랜드등록) |

### 8.2 인증 필요 대시보드
| URL | 파일 | 설명 |
|---|---|---|
| `/dashboard` | `dashboard.html` | 메인 대시보드 (게이지·KPI·위협 목록) |
| `/threats` | `threats.html` | 위협 상세 목록 (필터·정렬·재분석) |
| `/actions` | `actions.html` | 처리해야 할 사항 (미해결 위협 큐) |
| `/brand-image` | `brand-image.html` | 브랜드 이미지 점수 추이 |
| `/negative-mentions` | `negative-mentions.html` | 부정적 언급 피드백 |
| `/reports` | `reports.html` | 보고서 (일간·주간·월간 + PDF/PPT 다운로드) |
| `/history` | `history.html` | 처리 내역 + 아카이브 |
| `/settings` | `settings.html` | 키워드·프로파일·알림·구독 설정 |
| `/support` | `support.html` | 고객센터 게시판 |

### 8.3 조직 관련
| URL | 파일 | 설명 |
|---|---|---|
| `/orgs/new` | `org_create.html` | 조직 생성 |
| `/orgs/join` | `join.html` | 초대 코드로 조직 참여 |

### 8.4 디자인 시스템
```css
/* 폰트 */
영문 display: Syne (font-display)
한글 본문:    Noto Sans KR (font-body)
코드/수치:    JetBrains Mono (font-mono)

/* 색상 토큰 */
surface-0: #ffffff    surface-50: #f8fafc    surface-100: #f1f5f9
brand-500: #1a6ef8    navy: #0c1428

/* 위협 등급 색상 */
critical: #dc2626  high: #ea580c  medium: #d97706  low: #16a34a

/* 다크모드 */
localStorage('db-theme') = 'dark' | 'light'   (기본 dark)
html[data-theme="dark"] 속성으로 전환
```

---

## 9. 비동기 워커 (Celery)

### 9.1 Celery Beat 스케줄

| 태스크 | 주기 | 설명 |
|---|---|---|
| `collect_all_profiles` | 30분 | 전 플랫폼 병렬 수집 |
| `send_daily_reports` | 매일 09:00 KST | 일간 보고서 이메일 |
| `send_weekly_reports` | 매주 월요일 | 주간 보고서 이메일 |
| `purge_expired_data` | 매일 새벽 02:00 | 90일 경과 아카이브 삭제 |

### 9.2 주요 태스크

```python
# 수집
collect_all_profiles()         # 전체 브랜드 프로파일 병렬 수집
collect_single_profile(id)     # 단일 프로파일 즉시 수집
purge_expired_data()           # 만료 데이터 정리

# 분석
analyze_threat(threat_id)      # L3 심층 분석 단건

# 알림
send_immediate_alert(threat_id)  # Critical 즉시 Slack 알림
send_daily_reports()           # 일간 요약 이메일
send_weekly_reports()          # 주간 요약 이메일
```

### 9.3 인프라

```yaml
# railway.toml — 운영 환경
[deploy]
startCommand = "celery -A backend.workers.celery_app worker -B -c 2"

# docker-compose.yml — 로컬 개발
services: postgres + redis + worker + flower
```

---

## 10. 보고서 시스템

### 10.1 PDF 보고서 (ReportLab)

**생성 엔드포인트:** `GET /api/reports/{period}/pdf`

**구성 (8섹션 A4):**

| 섹션 | 내용 |
|---|---|
| 표지 | 브랜드명·기간·브랜드 이미지 점수·KPI 6개 |
| 1. 핵심 요약 | Executive Summary KPI 테이블·점수 상태 설명 |
| 2. 위협 현황 | 심각도별·플랫폼별·위협 유형 Top5 분포 바 차트 |
| 3. 감성·감정 | 긍정/중립/부정 분포·감정 분류·부정 언급 사례 |
| 4. 조직 공격·봇 | 조직적 공격 건수·봇 의심·플랫폼별 감성 분포 |
| 5. 미해결 위협 Top 10 | 카드 형태 상세 (계정·위험도·AI 권고) |
| 6. 조치 완료 내역 | 실제 해결 위협 목록·메모 |
| 7. 모니터링 현황 | 키워드·플랫폼·분석 엔진 정보 |
| 8. 대응 권고사항 | 위협 등급 기반 구체 권고 + AI 권고 |

**기술 특징:**
- 한국어 폰트: NanumGothic TTF 번들 (서버 폰트 없을 때 자동 탐색)
- 테이블 너비: 모두 180mm (A4 210mm - 좌우 여백 각 15mm)
- `wordWrap='CJK'` 적용으로 한국어 셀 텍스트 오버플로 방지
- 헤더·푸터 자동 삽입 (표지 제외)

### 10.2 PPT 보고서 (python-pptx)

**생성 엔드포인트:** `GET /api/reports/{period}/pptx`

**구성 (6슬라이드 16:9):**

| 슬라이드 | 내용 |
|---|---|
| 1. Cover | 브랜드명·기간·KPI 4개 박스 (NAVY 배경) |
| 2. 핵심 요약 | KPI 6개 그리드 + 브랜드 이미지 점수 |
| 3. 위협 현황 | 심각도별·플랫폼별 인라인 바 차트 |
| 4. 감성 분석 | 감성 분포 + 감정 분류 바 차트 |
| 5. 미해결 Top 5 | 테이블 형태 위협 목록 |
| 6. 권고사항 | 색상 헤더 + 설명 권고 카드 |

---

## 11. 조직 관리 시스템

### 11.1 구독 티어별 제한

| 티어 | 조직 수 | 설명 |
|---|---|---|
| free | 1개 | 기본 무료 |
| starter | 3개 | 스타터 플랜 |
| pro | 5개 | 프로 플랜 |
| enterprise | 무제한 | 엔터프라이즈 |

### 11.2 멤버 역할 (RBAC)

| 역할 | 권한 |
|---|---|
| owner | 전체 관리 (삭제 포함) |
| admin | 멤버 관리·설정 변경 |
| member | 스캔·위협 처리 가능 |
| viewer | 읽기 전용 |

### 11.3 가입 플로우

```
방법 1 — 초대 코드:
  관리자 → 코드 생성 (역할 지정·만료일·사용 횟수)
  → URL 공유 → 코드 입력 → 즉시 active

방법 2 — 승인 요청:
  사용자 → 참여 신청(pending)
  → 관리자 승인(active) / 거절(DB 삭제)
```

### 11.4 화이트라벨 지원

```
Organization 테이블:
  white_label_enabled: bool
  white_label_logo_url: string
  white_label_brand_name: string
  white_label_color: string (#RRGGBB)
```

---

## 12. 온보딩 플로우

### 3단계 온보딩 (`/onboarding`)

```
CustomerProfile 없으면 → 자동 리다이렉트

Step 1 — 경로 선택
  ├ 새 조직 만들기 → Step 2A (조직 이름·도메인 설정)
  └ 기존 조직 참여 → Step 2B (초대 코드 입력)

Step 2 — 조직 설정 / 참여

Step 3 — 브랜드 등록
  ├ 브랜드명 + 별칭 (공식·영문·약칭·별명)
  ├ 업종 선택 (뷰티/패션/식품/IT/금융/기타)
  ├ 공식 SNS 계정 등록 (Instagram·YouTube·X·TikTok·Naver)
  ├ 임직원 등록 (CEO·임원·직원)
  └ 모니터링 키워드 추가
```

---

## 13. 감성 분석 시스템

### 13.1 KNU 한국어 감성 사전

- **파일:** `backend/data/knu_senti_dict.txt` (14,854개 단어)
- **활용:** Gemini API 실패 시 폴백
- **모듈:** `backend/services/analyzers/sentiment_kr.py`
- **분류:** 긍정(positive) / 중립(neutral) / 부정(negative)

### 13.2 L2 감성 분석 폴백 체인

```
HyperCLOVA X (API 키 있을 때)
    ↓ 실패
Gemini 2.5 Flash Lite (유료 전환 완료)
    ↓ 실패
KNU 한국어 감성 사전 (오프라인, 항상 동작)
```

### 13.3 감정 분류 (7가지)

분노 / 공포 / 혐오 / 슬픔 / 놀람 / 기쁨 / 중립

---

## 14. 배포 구성

### 14.1 Vercel (API + 프론트엔드)

```python
# 진입점: app.py (main.py 수정은 Vercel 미반영)
# 로깅: print()만 Vercel 로그에 표시 (logging.info() 미표시)
# lifespan: Vercel에서 미작동 → DB 마이그레이션은 Railway에서 직접 실행

# 라우팅 예시 (app.py)
app.include_router(reports.router)

@app.get("/reports")
async def reports_page(request: Request):
    return FileResponse("frontend/pages/reports.html")
```

### 14.2 Railway (Celery 워커)

```toml
# railway.toml
[deploy]
startCommand = "celery -A backend.workers.celery_app worker -B -c 2"
```

### 14.3 환경 변수

```ini
# 데이터베이스
DATABASE_URL=postgresql+asyncpg://...     # Railway PostgreSQL

# AI API
ANTHROPIC_API_KEY=sk-ant-...             # Claude Haiku 4.5 (L3)
GEMINI_API_KEY=...                        # Gemini 2.5 Flash Lite (L2)
GOOGLE_VISION_API_KEY=...                 # Vision API (이미지 분석)
HYPERCLOVA_API_KEY=...                    # HyperCLOVA X (L2 기본)

# SNS 수집
NAVER_CLIENT_ID=...                       # Naver Search API
NAVER_CLIENT_SECRET=...
YOUTUBE_API_KEY=...                       # YouTube Data API v3
X_BEARER_TOKEN=...                        # X (Twitter) API v2

# OAuth
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
SECRET_KEY=...                            # JWT 서명 키

# 결제 (Polar)
POLAR_CHECKOUT_LINK_STARTER=https://...
POLAR_CHECKOUT_LINK_PRO=https://...
POLAR_WEBHOOK_SECRET=whsec_...

# 알림
SLACK_WEBHOOK_URL=https://hooks.slack.com/...

# 고객센터
SUPPORT_ADMIN_EMAILS=admin@example.com

# Redis / Celery
REDIS_URL=redis://...
```

### 14.4 datetime 주의사항

```python
# DB는 naive UTC 사용
# timezone.utc 사용 시 asyncpg DataError 발생
datetime.utcnow()   # ✅ 올바름
datetime.now(timezone.utc)  # ❌ asyncpg 오류
```

---

## 15. PWA (Progressive Web App)

```json
// frontend/manifest.json
{
  "name": "SAYbrand",
  "short_name": "SAYbrand",
  "start_url": "/dashboard",
  "display": "standalone",
  "icons": [
    {"src": "/assets/icons/icon-192.png", "sizes": "192x192"},
    {"src": "/assets/icons/icon-512.png", "sizes": "512x512"},
    {"src": "/assets/icons/icon-maskable-512.png", "purpose": "maskable"}
  ]
}
```

- Service Worker (`frontend/sw.js`)로 오프라인 캐시
- `frontend/assets/js/pwa.js`에서 설치 프롬프트 관리

---

## 16. 가격 모델

### 구독 티어 (Polar 결제)

| 티어 | 월 요금 | 주요 기능 |
|---|---|---|
| Free | 무료 | 키워드 5개, 조직 1개, PDF 다운로드 |
| Starter | 유료 | 키워드 20개, 조직 3개, Slack 알림 |
| Pro | 유료 | 키워드 무제한, 조직 5개, 화이트라벨 |
| Enterprise | 문의 | 맞춤 조직·무제한 모든 기능 |

**결제 플로우:**
```
사용자 → /billing/checkout/{plan}
→ Polar 체크아웃 링크 리다이렉트
→ 결제 완료 → Polar Svix 웹훅 발송
→ /billing/webhook (서명 검증: whsec_ prefix 제거 후 base64 decode)
→ DB subscription_tier 업데이트
```

---

## 17. 성공 지표 (KPI)

| 단계 | 지표 | 목표 |
|---|---|---|
| MVP (3개월) | 파일럿 고객 | 5개사 |
| v1.0 (6개월) | MRR | 2,000만원 |
| v2.0 (12개월) | 고객사 / NPS | 100개 / NPS 50+ |
| 정확도 | 오탐률 (False Positive) | < 10% |

---

## 18. 현재 구현 상태 요약

| 카테고리 | 상태 |
|---|---|
| 코어 AI 파이프라인 (L1→L2→L3) | ✅ 실동작 |
| 리스크 스코어링 엔진 | ✅ 실동작 |
| Naver 수집기 | ✅ 검증 완료 |
| YouTube·X 수집기 | ✅ API 키 있을 때 |
| Gemini L2 분석 | ✅ 유료 전환 완료 |
| Claude Haiku L3 분석 | ✅ API 키 있을 때 |
| KNU 감성 사전 폴백 | ✅ 항상 동작 |
| 조직 관리 (RBAC·초대코드·승인) | ✅ 실동작 |
| 온보딩 플로우 (3단계) | ✅ 실동작 |
| Google OAuth 인증 | ✅ 실동작 |
| Polar 결제·웹훅 | ✅ 실동작 |
| PDF 보고서 | ✅ 실동작 |
| PPT 보고서 | ✅ 신규 구현 |
| Slack 알림 | ✅ 실동작 |
| Celery 비동기 워커 | 🟡 Redis 환경 필요 |
| Instagram 수집기 | ❌ v1.1 |
| TikTok 수집기 | ❌ v1.1 |
| 이미지 분석 (pHash) | 🟡 엔진 구현, 미통합 |

---

## 19. 발표 포인트 요약

### 차별화 포인트
1. **3계층 AI 파이프라인**: L1 ($0 비용) → L2 (저비용) → L3 (고위협만) 순서로 AI 비용 최소화
2. **조직적 공격 자동 탐지**: 6개 지표 가중합으로 봇·조직적 공격 vs 실제 불만 구분
3. **한국 시장 특화**: KNU 감성 사전·커뮤니티어·초성 반어법 처리
4. **마케팅 위기 12개 카테고리**: 불매운동·캠페인역풍·갑질폭로 등 브랜드 특화 분류
5. **즉시 활용 가능한 AI 권고**: "SNS 공식 대응·보도자료·내부 조치" 3가지 구체 문구 자동 생성

### 기술적 강점
- FastAPI + SQLAlchemy 2.0 async: 높은 동시성 처리
- Celery + Redis: 30분 주기 자동 수집으로 거의 실시간
- Vercel + Railway 듀얼 배포: 서버리스 API + 상시 워커 분리
- PWA 지원: 모바일 앱처럼 설치 가능
- 다크모드 기본 적용

---

*이 문서는 2026-06-20 기준 코드베이스 전수 분석으로 자동 생성되었습니다.*  
*파일 경로: `C:/Users/user/Desktop/SAYbrand/PROJECT_OVERVIEW.md`*
