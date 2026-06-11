# 제품 소개 페이지 (모듈 A/B/C, 위협 인텔리전스 맵, AI 분석 파이프라인)

## 배경

랜딩페이지 footer "제품" 섹션의 5개 항목(모듈 A, 모듈 B, 모듈 C, 위협 인텔리전스 맵, API 연동)이
현재 랜딩페이지 내 앵커(`#features`, `#module-b`, `#module-c`, `#threat-map`, `#pipeline`)로
연결되어 단순 스크롤 이동만 한다. 각 제품을 자세히 설명하는 독립 페이지를 신설한다.

"대시보드"는 실제 앱(`/dashboard`, 로그인 필요)으로 계속 연결하며 이번 범위에서 제외한다.
고객센터/보안정책/개인정보처리방침/이용약관 페이지는 별도 작업으로 분리한다.

## 범위

5개 신규 정적 HTML 페이지:

| 경로 | 파일 | 주제 |
|---|---|---|
| `/products/module-a` | `frontend/pages/products/module-a.html` | 모듈 A — 브랜드 사칭 탐지 |
| `/products/module-b` | `frontend/pages/products/module-b.html` | 모듈 B — 가짜뉴스/조직적 공격 탐지 |
| `/products/module-c` | `frontend/pages/products/module-c.html` | 모듈 C — 감성·여론 분류 |
| `/products/threat-map` | `frontend/pages/products/threat-map.html` | 위협 인텔리전스 맵 |
| `/products/pipeline` | `frontend/pages/products/pipeline.html` | AI 분석 파이프라인 (L1/L2/L3) — footer "API 연동" |

## 라우팅

`main.py`에 `/` 와 동일한 패턴으로 공개(비로그인) GET 라우트 5개 추가:

```python
@app.get("/products/module-a")
async def product_module_a():
    return FileResponse("frontend/pages/products/module-a.html")
```
(나머지 4개 동일 패턴)

## 페이지 템플릿 구조

각 페이지는 `landing.html`과 동일한 `<head>`(manifest, theme-color, landing.css, pwa.js),
동일한 nav/모바일메뉴/footer 마크업, 동일한 인라인 JS(테마 토글, 햄버거,
스크롤 시 nav frosted glass, `.animate-section` 스크롤 인 애니메이션)를 그대로 포함한다.
새 CSS 클래스 추가는 최소화하고 기존 `ld-*` 클래스를 재사용한다.

페이지 본문 섹션 순서 (공통):

1. **히어로** — `ld-label`(예: `MODULE A · VISION AI`) + `ld-h2` 타이틀 + 한 줄 설명 +
   CTA 버튼(무료 체험 시작 `/login`, 영업팀 문의 `mailto:sales@saybrand.ai`)
2. **작동 방식** — 단계별 플로우 카드 (각 모듈 3~4단계)
3. **핵심 기능** — 기존 랜딩페이지 체크리스트/차별점 문구 재사용 + 보강
4. **데모 시각화** — 기존 랜딩페이지 데모 컴포넌트(`ld-threat-card-demo`, `bot-network-wrap` SVG,
   `ld-sentiment-demo`, `ld-map-demo`, `ld-pipeline-cards`) 재사용
5. **활용 시나리오** — 일반적 사용 흐름 서술 2~3개 (가짜 통계·수치 신규 생성 금지)
6. **FAQ** — 모듈별 3~4개 Q&A (`<details>`/`<summary>` 또는 단순 리스트, 신규 CSS 최소화)
7. **마무리 CTA** — 랜딩페이지 ⑧ 섹션과 동일한 CTA 블록 재사용

### 모듈별 작동 방식 단계 (초안)

- **모듈 A (사칭 탐지)**: SNS 계정/게시물 수집 → pHash·CLIP 로고 유사도 비교 →
  계정 행동 패턴(팔로워, 게시물 패턴) 분석 → 위협 등급 산정 및 신고 가이드 생성
- **모듈 B (가짜뉴스/조직적 공격)**: 게시물·댓글 수집 → 봇 확률·전파 속도 분석 →
  텍스트 유사성 군집화로 캠페인 탐지 → 조직적 공격 vs 일반 여론 구분
- **모듈 C (감성 분류)**: 게시물 수집 → KNU 감성사전(14,854개 어휘) 1차 분류 →
  Gemini 2.5 Flash 폴백 정밀 분석 → Critical~Feedback 5단계 위협 등급 분류
- **위협 인텔리전스 맵**: 전 플랫폼 위협 데이터 집계 → 플랫폼별 분포 시각화 →
  위협 유형 태그 클라우드 → 클릭 시 해당 플랫폼/유형 드릴다운 (대시보드 연결 안내)
- **AI 분석 파이프라인**: L1 규칙 기반 필터(키워드, 비용 $0, 70%) →
  L2 텍스트+이미지 분석(Gemini Flash + Vision API, 25%) →
  L3 Claude Haiku 4.5 심층 분석(고위협만, 5%)

## 랜딩페이지 변경

- footer "제품" 5개 링크: `#anchor` → `/products/...` 절대경로로 변경
  (대시보드 링크는 `/dashboard` 그대로 유지)
- 각 해당 섹션(`#features`, `#module-b`, `#module-c`, `#threat-map`, `#pipeline`)에
  "자세히 보기 →" 링크을 추가하여 대응하는 신규 페이지로 연결
- 섹션 자체의 기존 콘텐츠/구조/데모는 변경하지 않음

## 테스트

정적 HTML + FastAPI `FileResponse` 라우트이므로 별도 단위 테스트는 불필요.
`tests/` 내 기존 라우트 테스트 패턴이 있다면 5개 신규 GET 라우트가 200을 반환하는지
확인하는 테스트를 추가한다 (있을 경우에만).

## 비범위 (Out of scope)

- 고객센터(mailto), 보안정책, 개인정보처리방침, 서비스 이용약관 페이지 — 별도 작업
- 대시보드 소개 페이지 — `/dashboard` 링크 그대로 유지
- 신규 통계/수치 데이터 생성 (CLAUDE.md 투명성 원칙: Mock/실제 데이터 구분 필수,
  본 작업은 정적 마케팅 텍스트만 다루므로 가짜 수치 추가 금지)
