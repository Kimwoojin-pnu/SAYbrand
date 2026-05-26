# SAYbrand — Technical Requirements Document (TRD)

**버전:** 1.0.0  
**스택:** FastAPI + Tailwind CSS  
**목표 규모:** 100명 → 1,000명 확장 가능 설계

---

## 1. 기술 스택

| 레이어 | 기술 | 이유 |
|---|---|---|
| **Backend** | FastAPI (Python 3.11+) | 비동기 지원, 빠른 개발, 자동 API 문서 |
| **Frontend** | Tailwind CSS + Vanilla JS | 빌드 없이 CDN으로 즉시 사용 |
| **DB** | PostgreSQL (운영) / SQLite (개발) | 안정적, SQLAlchemy async 지원 |
| **ORM** | SQLAlchemy 2.0 (async) | 비동기 쿼리 |
| **캐시/큐** | Redis + Celery | 비동기 AI 분석 태스크 처리 |
| **AI — L2** | Gemini Flash / HyperCLOVA X DASH | 한국어 텍스트 분석 (저비용) |
| **AI — L3** | Claude Haiku 4.5 | 고위협 케이스 심층 분석 |
| **Image AI** | pHash (자체) + Google Vision API | 로고 유사도 탐지 |
| **서버** | Gunicorn + uvicorn workers | 멀티 워커 운영 |
| **컨테이너** | Docker + docker-compose | 환경 일관성 |
| **리버스 프록시** | Nginx | 로드밸런싱, SSL |

---

## 2. 프로젝트 구조

```
brandguard/
│
├── main.py                          # FastAPI 앱 진입점
├── config.py                        # 환경변수, 설정값
├── requirements.txt
├── .env                             # API 키, DB URL (git 제외)
├── docker-compose.yml
├── nginx.conf
│
├── backend/
│   ├── __init__.py
│   ├── config.py
│   │
│   ├── routers/                     # API 라우터
│   │   ├── __init__.py
│   │   ├── dashboard.py             # 대시보드 데이터 API
│   │   ├── threats.py               # 위협 CRUD
│   │   ├── alerts.py                # 알림 API
│   │   ├── reports.py               # 리포트 API
│   │   └── keywords.py              # 키워드 관리 API
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   │
│   │   ├── collectors/              # SNS 데이터 수집
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # 공통 Rate Limit 관리
│   │   │   ├── instagram.py
│   │   │   ├── youtube.py
│   │   │   ├── x_twitter.py
│   │   │   ├── tiktok.py
│   │   │   └── naver.py
│   │   │
│   │   ├── analyzers/               # AI 분석 3단계 레이어
│   │   │   ├── __init__.py
│   │   │   ├── l1_filter.py         # 규칙 기반 필터 (무료, 즉시)
│   │   │   ├── l2_text.py           # Gemini Flash / HyperCLOVA X
│   │   │   ├── l2_image.py          # pHash + Google Vision
│   │   │   └── l3_deep.py           # Claude Haiku (고위협 5%만)
│   │   │
│   │   ├── risk_scorer.py           # 리스크 스코어링 엔진
│   │   ├── notifier.py              # 알림 발송 (SMS/이메일/대시보드)
│   │   └── cache.py                 # Redis 캐싱 레이어
│   │
│   ├── workers/                     # Celery 비동기 태스크
│   │   ├── __init__.py
│   │   ├── celery_app.py
│   │   ├── collection_tasks.py      # SNS 수집 스케줄링
│   │   └── analysis_tasks.py        # AI 분석 큐잉
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── orm.py                   # SQLAlchemy ORM 모델
│   │   └── schemas.py               # Pydantic 스키마
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py              # AsyncPG + 세션 관리
│   │   └── redis_client.py          # Redis 연결
│   │
│   └── middleware/
│       ├── __init__.py
│       ├── rate_limiter.py          # API Rate Limiting
│       └── auth.py                  # 인증 미들웨어
│
├── frontend/
│   ├── pages/
│   │   ├── dashboard.html           # 메인 대시보드 ← MVP 핵심
│   │   ├── threats.html             # 위협 상세 목록
│   │   ├── reports.html             # 리포트 페이지
│   │   └── settings.html            # 키워드·알림 설정
│   │
│   └── assets/
│       ├── css/
│       │   └── custom.css
│       └── js/
│           ├── api.js               # fetch 래퍼, 공통 API 호출
│           ├── dashboard.js         # 대시보드 로직
│           └── utils.js             # 공통 유틸 (timeAgo, badge 등)
│
└── tests/
    ├── test_risk_scorer.py
    ├── test_l1_filter.py
    └── test_api.py
```

---

## 3. 데이터베이스 스키마

### users
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | |
| name | VARCHAR(100) | |
| email | VARCHAR(200) UNIQUE | |
| company | VARCHAR(200) | |
| user_type | VARCHAR(50) | influencer / brand / enterprise |
| created_at | DATETIME | |

### threats
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | |
| user_id | INTEGER FK | |
| module | CHAR(1) | A / B / C |
| threat_type | VARCHAR(100) | logo_spoof / organized_rumor / ... |
| severity | VARCHAR(20) | critical / high / medium / low |
| platform | VARCHAR(50) | instagram / x / youtube / ... |
| source_account | VARCHAR(200) | |
| source_url | VARCHAR(500) | |
| content_preview | TEXT | |
| confidence | FLOAT | 0.0 ~ 1.0 |
| risk_score | INTEGER | 0 ~ 100 |
| ai_analysis | TEXT | L3 분석 결과 |
| ai_response_suggestion | TEXT | 대응 방안 |
| status | VARCHAR(20) | active / reviewing / resolved |
| detected_at | DATETIME | |
| updated_at | DATETIME | |

### alerts
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | |
| threat_id | INTEGER FK | |
| severity | VARCHAR(20) | |
| message | TEXT | |
| channel | VARCHAR(50) | sms / email / dashboard |
| sent_at | DATETIME | |

### keywords
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | |
| user_id | INTEGER FK | |
| keyword | VARCHAR(200) | |
| platforms | JSON | ["instagram", "x"] |
| active | BOOLEAN | |
| created_at | DATETIME | |

---

## 4. API 엔드포인트

### Dashboard
```
GET  /api/dashboard/stats          전체 통계 (위협 수, 등급별)
GET  /api/dashboard/risk-score     리스크 스코어 상세 (모듈별)
GET  /api/dashboard/threats        위협 목록 (필터, 페이지네이션)
GET  /api/dashboard/alerts         최근 알림 목록
PATCH /api/dashboard/threats/{id}/status  위협 상태 변경
```

### Keywords
```
GET    /api/keywords               키워드 목록
POST   /api/keywords               키워드 등록
DELETE /api/keywords/{id}          키워드 삭제
```

### Reports
```
GET  /api/reports/daily            일간 리포트
GET  /api/reports/weekly           주간 리포트
```

### WebSocket
```
WS   /ws/alerts                    실시간 알림 스트림
```

---

## 5. AI 분석 파이프라인

```
SNS 콘텐츠 수집 (Celery 스케줄러)
        ↓
[L1] 규칙 기반 필터           → 비용 $0 | 처리량 70%
  키워드 매칭, 계정명 패턴, 반복 문자
        ↓ (30% 통과)
[L2] 텍스트: Gemini Flash     → 저비용  | 처리량 25%
     이미지: pHash + Vision   → 저비용
  감성 분석, 봇 확률 계산
        ↓ (5% 고위협)
[L3] Claude Haiku 4.5         → 고비용  | 처리량 5%
  심층 분석 + 대응 전략 생성
        ↓
리스크 스코어 산출 → DB 저장 → 알림 발송
```

---

## 6. 리스크 스코어링 로직

```python
# 단일 위협 점수
risk_score = severity_weight × module_weight × platform_weight × confidence

# 가중치 테이블
severity:  critical=1.0, high=0.7, medium=0.4, low=0.15
module:    A=1.0 (사칭), B=0.85 (루머), C=0.7 (임직원)
platform:  instagram=1.0, youtube=0.9, tiktok=0.85, x=0.8, naver=0.7

# 조직적 공격 시 30% 가산
if is_organized: risk_score = min(risk_score * 1.3, 100)

# 전체 브랜드 위협 지수
overall = module_a_avg × 0.40 + module_b_avg × 0.35 + module_c_avg × 0.25
```

---

## 7. 봇 탐지 알고리즘

```python
bot_probability = (
  account_age_score    × 0.30  # 계정 생성일 (30일 기준)
  + similar_text_score × 0.25  # 유사 텍스트 게시물 수
  + velocity_score     × 0.25  # 시간당 전파 속도
  + engagement_score   × 0.20  # 팔로워 대비 참여율 이상
)
# bot_probability > 0.7 → 조직적 공격으로 판단
```

---

## 8. 확장성 설계 (1,000명 기준)

### 비동기 처리
- FastAPI async + AsyncPG (동기 블로킹 없음)
- Celery + Redis로 AI 분석 태스크 분리
- Gunicorn 멀티 워커 운영

### 캐싱 전략
- Redis: 동일 콘텐츠 분석 결과 캐시 (TTL 1시간)
- 같은 바이럴 콘텐츠 → 1번만 분석, 비용 절감

### Rate Limit 관리
- SNS API 요청 → 플랫폼별 제한 내 스케줄링
- 사용자 API 요청 → 분당 60회 제한 (미들웨어)

### 비용 구조 (100명 기준 월 ~$91)
```
L1 필터      $0    (자체)
L2 텍스트    $4    (Gemini Flash)
L2 이미지    $12   (Google Vision 10%만)
L3 심층      $18   (Claude Haiku, 5%만)
인프라       $57   (서버/DB/Redis)
```

---

## 9. 보안 · 법적 준수

### 개인정보보호법(PIPA) 준수
- 공개 SNS 데이터만 수집 (비공개 계정 접근 금지)
- 개인식별정보(PII) 비식별화 처리 후 저장
- 데이터 보존 기간: 수집 후 90일
- `.env`에 API 키 관리 (코드에 하드코딩 금지)

### SNS 플랫폼 ToS 준수
- 공식 API만 사용 (스크래핑 금지)
- Rate Limit 엄수
- 플랫폼별 허용 데이터 범위 내에서만 활용

---

## 10. 환경변수 (.env)

```env
# 앱
APP_NAME=SAYbrand
APP_ENV=development  # development / production

# DB
DATABASE_URL=sqlite+aiosqlite:///./brandguard.db
# 운영: postgresql+asyncpg://user:pass@host:5432/brandguard

# Redis
REDIS_URL=redis://localhost:6379/0

# AI API
ANTHROPIC_API_KEY=         # Claude Haiku (L3)
GEMINI_API_KEY=             # Gemini Flash (L2)
GOOGLE_VISION_API_KEY=      # 이미지 분석

# Rate Limit
RATE_LIMIT_PER_MINUTE=60
```

---

## 11. 개발 순서 (Critical Path)

```
Phase 1 — 뼈대 (1주)
  ✅ FastAPI 앱 구조
  ✅ DB 모델 + 스키마
  ✅ Mock 데이터 시드

Phase 2 — 대시보드 (2주)  ← 현재
  ✅ 메인 대시보드 UI
  ✅ 위협 목록 + 상세 모달
  ✅ 리스크 스코어 게이지
  ✅ 실시간 알림 피드

Phase 3 — AI 엔진 (2주)
  ✅ L1 규칙 필터
  ✅ L3 Claude Haiku 연동
  □ L2 Gemini Flash 연동
  □ 이미지 pHash 구현

Phase 4 — 수집 파이프라인 (3주)
  □ Instagram Graph API
  □ YouTube Data API
  □ X API v2
  □ Celery 스케줄러

Phase 5 — 알림·리포트 (1주)
  □ 이메일 알림
  □ 일간/주간 리포트
  □ 키워드 설정 UI
```

---

## 12. 실행 방법

```bash
# 개발 환경
pip install -r requirements.txt
cp .env.example .env     # API 키 입력
uvicorn main:app --reload

# 운영 환경
docker-compose up -d
```

접속: `http://localhost:8000`
