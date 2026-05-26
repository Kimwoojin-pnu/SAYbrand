# CLAUDE.md — SAYbrand 개발 지침

Claude Code가 이 프로젝트를 개발할 때 반드시 따라야 할 행동 지침.  
**PRD.md**와 **TRD.md**를 먼저 읽고 전체 맥락을 파악한 뒤 작업할 것.

---

## 1. 코딩 원칙

### 추측하지 말고 문서를 따를 것
- 기능 구현 전 PRD.md에서 요구사항 확인
- 기술 결정 전 TRD.md에서 설계 방향 확인
- 문서에 없는 내용이면 구현하지 말고 질문할 것

### 요청한 것만 만들 것
- 요청하지 않은 기능 추가 금지
- "있으면 좋을 것 같은" 코드 추가 금지
- 단일 책임 — 함수 하나는 하나의 일만

### 건드려야 할 곳만 건드릴 것
- 수정 요청 받은 파일 외 다른 파일 임의 수정 금지
- 기존 스타일·컨벤션 유지 (내 스타일로 바꾸지 말 것)
- 내 변경으로 생긴 orphan (미사용 import 등)만 정리

---

## 2. 기술 스택 (변경 금지)

```
Backend:   FastAPI (Python 3.11+) + SQLAlchemy 2.0 async
Frontend:  Tailwind CSS (CDN) + Vanilla JS (빌드 없음)
DB:        SQLite (개발) / PostgreSQL (운영)
Cache:     Redis + Celery
AI L2:     Gemini Flash API (google-generativeai)
AI L3:     Claude Haiku 4.5 (anthropic)
이미지:    imagehash (pHash) + Google Vision API
```

스택 변경이 필요하다고 판단되면 먼저 이유를 설명하고 승인받을 것.

---

## 3. 파일 구조 (TRD.md 기준)

```
brandguard/
├── main.py
├── backend/
│   ├── config.py
│   ├── routers/      (dashboard, threats, alerts, reports, keywords)
│   ├── services/
│   │   ├── collectors/    (instagram, youtube, x_twitter, tiktok, naver)
│   │   ├── analyzers/     (l1_filter, l2_text, l2_image, l3_deep)
│   │   ├── risk_scorer.py
│   │   ├── notifier.py
│   │   └── cache.py
│   ├── workers/      (celery_app, collection_tasks, analysis_tasks)
│   ├── models/       (orm, schemas)
│   ├── db/           (database, redis_client)
│   └── middleware/   (rate_limiter, auth)
├── frontend/
│   ├── pages/        (dashboard, threats, reports, settings)
│   └── assets/       (css, js)
└── tests/
```

새 파일 추가 시 이 구조를 따를 것.

---

## 4. AI API 사용 규칙

### 반드시 레이어드 방식으로 호출할 것

```
L1 먼저 → 통과한 것만 L2 → 고위협만 L3
```

L3(Claude Haiku)를 모든 콘텐츠에 호출하는 코드는 잘못된 구현.

### API 키는 환경변수로만
```python
# 올바름
from backend.config import settings
client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

# 금지
client = anthropic.AsyncAnthropic(api_key="sk-ant-...")
```

### API 키 없을 때 graceful fallback
```python
if not settings.anthropic_api_key:
    return _mock_analysis(...)  # Mock으로 대체, 에러 발생 금지
```

---

## 5. 비동기 필수

모든 DB 쿼리, 외부 API 호출은 async/await 사용.

```python
# 올바름
async def get_threats(db: AsyncSession):
    result = await db.execute(select(Threat))
    return result.scalars().all()

# 금지 — 동기 블로킹
def get_threats(db: Session):
    return db.query(Threat).all()
```

---

## 6. 리스크 스코어링 — 임의 수정 금지

`backend/services/risk_scorer.py`의 가중치 테이블은 설계에서 확정된 값.  
수정 필요 시 반드시 이유 설명 후 승인받을 것.

```python
SEVERITY_WEIGHTS = {
    "critical": 1.0,
    "high":     0.7,
    "medium":   0.4,
    "low":      0.15,
}

MODULE_WEIGHTS = {"A": 1.0, "B": 0.85, "C": 0.7}
PLATFORM_WEIGHTS = {"instagram": 1.0, "youtube": 0.9, "tiktok": 0.85, "x": 0.8, "naver": 0.7}
```

---

## 7. 프론트엔드 규칙

### Tailwind CDN 사용 (빌드 없음)
```html
<script src="https://cdn.tailwindcss.com"></script>
```
npm, webpack, vite 등 빌드 도구 사용 금지.

### 폰트
```
영문 display: Syne (font-display)
한글 본문:    Noto Sans KR (font-body)
코드/수치:    JetBrains Mono (font-mono)
```

### 디자인 토큰
```css
/* 배경 */
surface-0: #ffffff
surface-50: #f8fafc
surface-100: #f1f5f9

/* 브랜드 */
brand-500: #1a6ef8

/* 위협 등급 */
critical: #dc2626 (빨강)
high:     #ea580c (주황)
medium:   #d97706 (황색)
low:      #16a34a (초록)
```

### JS — fetch 래퍼 사용
`frontend/assets/js/api.js`에 공통 fetch 함수 정의 후 재사용.  
각 페이지에서 직접 `fetch('/api/...')` 중복 작성 금지.

---

## 8. 에러 처리

```python
# API 라우터에서 명시적 상태 코드
from fastapi import HTTPException

result = await db.execute(select(Threat).where(Threat.id == id))
threat = result.scalar_one_or_none()
if not threat:
    raise HTTPException(status_code=404, detail="Threat not found")
```

외부 API 실패는 항상 try/except로 감싸고 Mock으로 fallback:
```python
try:
    result = await call_external_api(...)
except Exception as e:
    logger.warning(f"External API failed: {e}")
    result = mock_fallback()
```

---

## 9. 테스트

새 비즈니스 로직 구현 시 `tests/` 에 테스트 추가.  
최소 커버리지: 리스크 스코어링, L1 필터, API 엔드포인트.

```bash
pytest tests/ -v
```

---

## 10. 커밋 메시지 형식

```
feat: 위협 상태 변경 API 추가
fix: 리스크 스코어 계산 오류 수정
refactor: L1 필터 배치 처리 성능 개선
docs: API 엔드포인트 주석 추가
```

---

## 11. MVP 완료 기준

다음 항목을 모두 만족해야 MVP 완성으로 간주:

- [ ] `uvicorn main:app --reload` 실행 시 에러 없이 기동
- [ ] `http://localhost:8000` 접속 시 대시보드 렌더링
- [ ] 위협 목록 API (`/api/dashboard/threats`) 정상 응답
- [ ] 리스크 스코어 게이지 표시
- [ ] 위협 클릭 → 상세 모달 → 상태 변경 동작
- [ ] `.env`에 `ANTHROPIC_API_KEY` 입력 시 L3 분석 실제 동작
- [ ] API 키 없어도 Mock으로 정상 동작

---

## 주의사항

1. **API 키를 코드에 직접 쓰지 말 것** — `.env`만 사용
2. **동기 DB 쿼리 쓰지 말 것** — 반드시 async
3. **L3를 모든 콘텐츠에 호출하지 말 것** — 비용 폭발
4. **빌드 도구 추가하지 말 것** — Tailwind CDN으로 충분
5. **스키마 임의 변경 금지** — DB 마이그레이션 필요

---

## 12. 구현 상태 투명성 원칙

이 프로젝트의 목표는 실제 판매 가능한 서비스다.
절대 되는 척하거나 숨기지 말 것.

### 필수 규칙

**Mock과 실제를 항상 명확히 구분한다**
- Mock 데이터로 동작하는 기능은 코드 주석과
  PROGRESS.md에 반드시 "[MOCK]" 표기
- API 키 없이 돌아가는 것 = 작동하는 것이 아님
- "연동 완료"는 실제 API 호출이 성공한 경우만 사용

**완료 선언 금지 조건**
아래 중 하나라도 해당하면 완료 선언 불가:
- 실제 데이터 없이 Mock만 표시되는 기능
- API 키 입력해도 실제 호출이 실패하는 기능
- UI는 있지만 백엔드 연결이 안 된 기능
- 에러를 try/except로 숨기고 Mock 반환하는 기능

**PROGRESS.md 상태 표기 기준**
- ✅ 완료: 실제 데이터로 end-to-end 동작 검증됨
- 🟡 Mock: UI/로직은 있으나 실제 데이터 미연결
- ❌ 미구현: 디렉토리/파일만 존재하거나 stub 상태
- ⚠️ 불안정: 동작하나 엣지케이스 미처리

**UNSEEN_CHANGES.md 기록 기준**
실제로 동작하지 않는 기능을 구현한 척 기록 금지.
Mock 처리한 경우 "[MOCK]" 태그 반드시 포함.

### 현재 시점 실제 동작 현황 즉시 업데이트
PROGRESS.md를 위 기준으로 전면 재검토하고
모든 항목의 상태를 ✅ / 🟡 / ❌ / ⚠️ 로 재표기할 것.
