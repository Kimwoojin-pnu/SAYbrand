## Claude.ai 확인 기준
- SNAPSHOT.md (2026-05-18 v3) 확인 완료
- pipeline·수집기·L1/L2 구현 완료 확인
- 원칙: 되는 척 금지. Mock은 [MOCK] 명시.

## 작업 요청 — 프론트엔드 완성 + 검증 + 배포 준비

아래 순서대로 진행. 각 단계 완료 시 PROGRESS.md 업데이트.

---

### Step 1. 파이프라인 실제 동작 확인 (먼저 실행)

코드 작성 전 실제 동작 먼저 검증:

```bash
uvicorn main:app --reload
# 별도 터미널에서:
curl -X POST http://localhost:8000/api/dashboard/scan-local
curl http://localhost:8000/api/dashboard/threats
```

확인할 것:
- Threat 레코드가 실제로 DB에 생성되는가
- source_url 컬럼에 원본 링크가 있는가
- is_mock 여부 정확히 표기되는가

결과에 따라:
- 정상 → Step 2로 진행
- 에러 → 에러 내용 먼저 보고 후 수정

---

### Step 2. 대시보드 시각화 완성

`frontend/pages/dashboard.html` + `frontend/assets/js/dashboard.js` 수정

#### 2-1. Chart.js 트렌드 그래프
```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
```

GET /api/dashboard/trend 엔드포인트 (backend/routers/dashboard.py에 추가):
```python
@router.get("/api/dashboard/trend")
async def get_trend(days: int = 7, db=Depends(get_db), user=Depends(get_current_user)):
    # 최근 N일 날짜별 모듈A/B/C 위협 건수
    # 데이터 없으면 빈 배열 반환 (에러 아님)
    return {
        "labels": ["6일전", "5일전", ..., "오늘"],
        "module_a": [3, 5, 4, 7, 6, 8, 5],
        "module_b": [5, 4, 8, 6, 9, 7, 6],
        "module_c": [2, 3, 2, 4, 3, 5, 4],
        "is_mock": bool,
    }
```

차트 스타일 (DESIGN_SYSTEM 기준):
```javascript
const trendChart = new Chart(ctx, {
    type: 'line',
    data: {
        datasets: [
            { label: '모듈 A (사칭)', borderColor: '#E24B4A',
              backgroundColor: 'rgba(226,75,74,0.08)', tension: 0.4, fill: true },
            { label: '모듈 B (루머)', borderColor: '#BA7517',
              backgroundColor: 'rgba(186,117,23,0.08)', tension: 0.4, fill: true },
            { label: '모듈 C (임직원)', borderColor: '#185FA5',
              backgroundColor: 'rgba(24,95,165,0.08)', tension: 0.4, fill: true },
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            tooltip: {
                backgroundColor: '#0c1428',
                cornerRadius: 4,
            }
        },
        scales: {
            y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.04)' } }
        }
    }
})
```

데이터 없을 때 빈 상태:
"수집 후 7일이 지나면 트렌드를 확인할 수 있습니다."
→ 흰 화면/에러 절대 없음

#### 2-2. 플랫폼별 언급량 현황
GET /api/dashboard/platform-stats 엔드포인트:
```python
@router.get("/api/dashboard/platform-stats")
async def get_platform_stats(db=Depends(get_db), user=Depends(get_current_user)):
    # platform별 위협 건수 집계
    return {
        "platforms": [
            {"name": "Instagram", "platform": "instagram",
             "count": 12, "pct": 72, "negative_ratio": 68},
            {"name": "X (트위터)", "platform": "x",
             "count": 8, "pct": 52, "negative_ratio": 55},
            ...
        ],
        "is_mock": bool,
    }
```

플랫폼 행 클릭 시 해당 플랫폼으로 위협 목록 필터링.

#### 2-3. 위협 상세 슬라이드오버 패널
위협 행 클릭 → 우측에서 420px 패널 슬라이드인.

패널 구성:
```html
<div id="detail-panel">
    <!-- 심각도 배지 + 플랫폼 -->
    <span class="severity-badge" id="dp-severity"></span>
    <span id="dp-platform"></span>

    <!-- 계정 + 원본 링크 -->
    <h2 id="dp-account"></h2>
    <a id="dp-source-link" href="#" target="_blank">
        🔗 원본 게시글 보기
    </a>
    <!-- source_url 없으면 버튼 숨김 (없는 척 금지) -->

    <!-- 탐지 내용 -->
    <div id="dp-content"></div>

    <!-- AI 분석 (is_mock이면 [데모 분석] 표시) -->
    <div id="dp-analysis" class="ai-section"></div>

    <!-- 리스크 지표 4개 그리드 -->
    <div class="metrics-grid">
        <div>리스크 점수 <span id="dp-score"></span></div>
        <div>신뢰도 <span id="dp-confidence"></span></div>
        <div>봇 확률 <span id="dp-bot"></span></div>
        <div>공격 유형 <span id="dp-verdict"></span></div>
    </div>

    <!-- 대응 방안 -->
    <div id="dp-response"></div>

    <!-- 상태 변경 버튼 -->
    <button onclick="updateStatus('reviewing')">검토 중</button>
    <button onclick="updateStatus('resolved')">✓ 해결 완료</button>
</div>
```

슬라이드 애니메이션:
```css
#detail-panel {
    position: fixed; top: 0; right: 0;
    width: 420px; height: 100vh;
    transform: translateX(100%);
    transition: transform 0.28s cubic-bezier(0.4,0,0.2,1);
    background: #fff;
    box-shadow: rgba(12,20,40,0.20) -4px 0 24px;
    z-index: 40; overflow-y: auto;
}
#detail-panel.open { transform: translateX(0); }
```

#### 2-4. 실시간 업데이트 + Mock 배지
30초 폴링:
```javascript
setInterval(async () => {
    await loadDashboard()
    updateLastUpdated()
}, 30000)
```

Mock 데이터 사용 중 배지:
```html
<!-- is_mock=true인 데이터 있을 때만 표시 -->
<div id="mock-banner" style="display:none">
    ⚠️ 현재 데모 데이터를 표시 중입니다.
    API 키를 설정하면 실제 데이터를 수집합니다.
</div>
```

#### 2-5. 토스트 알림
새 위협 탐지 또는 스캔 완료 시:
```javascript
function showToast(message, severity = 'info') {
    // 우측 하단 slide-in
    // 4초 후 자동 fade-out
    // severity에 따라 border-left 색상 변경
}
```

---

### Step 3. 랜딩 페이지 생성

`frontend/pages/landing.html` 신규 생성.
DESIGN_SYSTEM.md 100% 적용.

구성 (9개 섹션):
① 탑 네비게이션 (sticky)

SAYbrand 로고 (assets/SAYbrand_로고.png)
중앙: 제품 / 솔루션 / 요금
우측: [로그인] + [무료 시작]

② 히어로 섹션

헤드라인: "당신의 브랜드를 / 24시간 지키는 AI의 눈"
서브: "사칭 계정, 가짜뉴스, 조직적 공격까지 — SAYbrand AI가
SNS 전 영역에서 위협을 사전 탐지합니다."
CTA: [14일 무료 체험] + [데모 보기]
우측: 대시보드 목업 이미지 + 오버레이 카드 2개
• 리스크 스코어 카드 (좌상단, 다크 배경)
• 위협 탐지 알림 카드 (우하단, 라이트 배경)
카드 등장: 페이지 로드 1초 후 순차 slide-in 애니메이션

③ 스탯 바

모니터링 키워드 12,400+ / 일일 분석 9.2M / 탐지 시간 47초 / NPS 67
뷰포트 진입 시 카운트업 애니메이션

④ 모듈 A 피처 (라이트, 2컬럼)

헤딩: "변형된 로고도 놓치지 않습니다"

⑤ 모듈 B 피처 (라이트, 2컬럼 reversed)

헤딩: "조직적 공격과 진짜 불만을 구분합니다"

⑥ AI 파이프라인 다크 섹션 (#0c1428)

L1 / L2 / L3 카드 3개
"비용 80% 절감" 포인트

⑦ 가격 섹션 (Starter / Pro / Enterprise)
⑧ CTA 마무리
⑨ 푸터 (#0c1428)

마이크로 인터랙션:
```javascript
// 스크롤 진입 애니메이션
const observer = new IntersectionObserver((entries) => {
    entries.forEach(el => {
        if (el.isIntersecting) {
            el.target.classList.add('visible')
            observer.unobserve(el.target)
        }
    })
}, { threshold: 0.15 })
document.querySelectorAll('.animate-section').forEach(el => observer.observe(el))

// 버튼 hover 부상
.btn-dark:hover { transform: translateY(-1px); }

// 네비 스크롤 frosted glass
window.addEventListener('scroll', () => {
    nav.style.backdropFilter = scrollY > 40 ? 'blur(12px)' : 'none'
})
```

main.py에 랜딩 라우트 추가:
```python
@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    # 로그인 상태면 대시보드로 리다이렉트
    session = request.session.get("user")
    if session:
        return RedirectResponse("/dashboard")
    return templates.TemplateResponse("pages/landing.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    # 미로그인 시 로그인으로
    session = request.session.get("user")
    if not session:
        return RedirectResponse("/login")
    return templates.TemplateResponse("pages/dashboard.html", {"request": request})
```

---

### Step 4. 누락 페이지 생성

#### frontend/pages/threats.html
위협 목록 전용 페이지:
- 날짜 범위 필터
- 심각도 / 모듈 / 플랫폼 / 상태 필터
- 테이블 + 슬라이드오버 (dashboard.html과 동일 컴포넌트)
- "데이터 없음" 빈 상태 친절하게

#### frontend/pages/reports.html
리포트 페이지:
- 일간 / 주간 탭
- 수집 기간 내 위협 요약 (건수, 등급별, 플랫폼별)
- "이메일 발송" 버튼 → [개발 예정] 표시 (없는 척 금지)
- Mock 데이터로 시연 가능

---

### Step 5. 이메일 알림 구현

`backend/services/notifier.py` 실제 구현:

```python
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from backend.config import settings

async def send_alert_email(user_email: str, threat, severity: str):
    if not settings.smtp_host or not settings.smtp_user:
        logger.warning("[MOCK] SMTP 미설정 — 이메일 발송 생략")
        return False  # 조용히 실패, 서비스 중단 없음

    subject_map = {
        "critical": f"🚨 [SAYbrand] 긴급 위협 탐지 — {threat.platform}",
        "high":     f"⚠️ [SAYbrand] 높은 위험 감지 — {threat.platform}",
    }

    html_body = f"""
    <div style="font-family: sans-serif; max-width: 600px;">
        <h2 style="color: #0c1428;">SAYbrand 위협 알림</h2>
        <div style="background: #fef2f2; border-left: 4px solid #E24B4A; padding: 16px;">
            <strong>{threat.severity.upper()}</strong> — {threat.platform}
        </div>
        <p>{threat.content_preview}</p>
        {'<p><a href="' + threat.source_url + '">원본 게시글 보기</a></p>'
         if threat.source_url else ''}
        <p style="color: #666;">{threat.ai_analysis or ''}</p>
        <a href="https://saybrand.ai/dashboard"
           style="background:#0c1428; color:white; padding:10px 20px;
                  text-decoration:none; border-radius:4px;">
            대시보드에서 확인
        </a>
    </div>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject_map.get(severity, "[SAYbrand] 위협 알림")
        msg["From"] = settings.smtp_user
        msg["To"] = user_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.smtp_host, 587) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"이메일 발송 실패: {e}")
        return False
```

---

### Step 6. 빈 상태 처리 전체 점검

모든 페이지에서 데이터 0건일 때 흰 화면/에러 없이
친절한 안내 표시:

```javascript
// 위협 0건
if (threats.length === 0) {
    list.innerHTML = `
        <div class="empty-state">
            <p>아직 탐지된 위협이 없습니다.</p>
            <p>스캔을 실행하거나 키워드를 등록해주세요.</p>
            <button onclick="triggerScan()">스캔 실행</button>
        </div>
    `
}
```

---

### Step 7. SKILL.md 자가 검증

모든 작업 완료 후 반드시 실행.

페르소나:
"뷰티 브랜드 홍보팀장, 비개발자.
경쟁사 솔루션 대신 SAYbrand 검토 중.
랜딩 페이지를 처음 봤고, 14일 무료 체험 시작함.
오늘 사칭 계정 제보 받아서 대시보드 접속.
30분 내 법무팀에 보고서 전달해야 함."

시나리오:
1. 랜딩 페이지 → 30초 내 서비스 가치 이해 가능한가
2. 회원가입 → 대시보드 → 핵심 위협 파악 → 3클릭 이내
3. 위협 클릭 → 원본 링크 → 법무팀 전달 가능한 정보 확인
4. 스캔 실행 → 결과 표시 → 피드백 명확한가
5. API 키 없어도 [MOCK] 표시로 서비스 흐름 이해 가능한가

7개 기준 전부 PASS 후 완료 선언.
FAIL 즉시 수정 → 재검증 (최대 3회).

---

### 작업 순서 요약
Step 1: scan-local 실제 동작 확인 (필수)
Step 2: 대시보드 차트 + 슬라이드오버
Step 3: 랜딩 페이지
Step 4: threats.html + reports.html
Step 5: 이메일 알림
Step 6: 빈 상태 처리
Step 7: SKILL.md 검증

---

### 최종 완료 기준

- [ ] scan-local → DB에 실제 Threat 저장 확인
- [ ] 트렌드 차트 + 플랫폼 차트 렌더링
- [ ] 위협 클릭 → 슬라이드오버 → source_url 표시
- [ ] 랜딩 페이지 9개 섹션 완성
- [ ] threats.html + reports.html 생성
- [ ] 이메일: SMTP 키 없어도 에러 없이 [MOCK] 처리
- [ ] 모든 빈 상태 친절한 안내
- [ ] SKILL.md 7/7 PASS
- [ ] PROGRESS.md + UNSEEN_CHANGES.md 업데이트