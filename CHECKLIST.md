# SAYbrand — 실행 전 체크리스트

복사해서 하나씩 체크하며 진행하세요.

---

## 1단계 — Google OAuth 앱 등록

- [ ] [Google Cloud Console](https://console.cloud.google.com/) 접속
- [ ] 새 프로젝트 생성 (또는 기존 프로젝트 선택)
- [ ] **API 및 서비스 → OAuth 동의 화면** 설정
  - 앱 이름: `SAYbrand`
  - 사용자 유형: 외부
  - 테스트 사용자에 본인 Gmail 추가 (심사 전까지 필요)
- [ ] **API 및 서비스 → 사용자 인증 정보 → OAuth 2.0 클라이언트 ID 생성**
  - 애플리케이션 유형: 웹 애플리케이션
  - 승인된 리다이렉션 URI 추가:
    - `http://localhost:8000/auth/callback` (로컬용)
    - `https://<your-domain>.vercel.app/auth/callback` (배포 후 추가)
- [ ] 클라이언트 ID와 클라이언트 시크릿을 복사

---

## 2단계 — Polar.sh 설정 (결제 기능 사용 시)

- [ ] [Polar.sh](https://polar.sh) 계정 생성 및 조직 생성
- [ ] 상품(Product) 생성 → Product ID 복사
- [ ] **Settings → Webhooks → Add Endpoint** 설정
  - URL: `https://<your-domain>.vercel.app/billing/webhook`
  - Events: `subscription.created`, `subscription.updated`, `subscription.cancelled` 체크
  - Webhook Secret 복사
- [ ] **Settings → Developers → API Tokens** 에서 Access Token 생성 후 복사

> 결제 기능 불필요 시 POLAR_* 키는 비워둬도 됩니다.

---

## 3단계 — .env 파일 채우기

`.env` 파일을 열어 아래 항목을 입력하세요.

```
GOOGLE_CLIENT_ID=          ← 1단계에서 복사한 클라이언트 ID
GOOGLE_CLIENT_SECRET=      ← 1단계에서 복사한 클라이언트 시크릿
SESSION_SECRET_KEY=        ← 랜덤 문자열 (예: openssl rand -hex 32)

POLAR_ACCESS_TOKEN=        ← 2단계에서 복사한 API 토큰
POLAR_WEBHOOK_SECRET=      ← 2단계에서 복사한 Webhook 시크릿
POLAR_PRODUCT_ID=          ← 2단계에서 복사한 Product ID

ANTHROPIC_API_KEY=         ← (선택) Claude L3 분석 활성화
GEMINI_API_KEY=            ← (선택) Gemini L2 분석 활성화
```

- [ ] `GOOGLE_CLIENT_ID` 입력
- [ ] `GOOGLE_CLIENT_SECRET` 입력
- [ ] `SESSION_SECRET_KEY` 랜덤 값 생성 및 입력
- [ ] Polar.sh 키 입력 (선택)
- [ ] AI API 키 입력 (선택 — 없으면 Mock으로 동작)

---

## 4단계 — 로컬 실행 확인

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

- [ ] `uvicorn` 실행 시 에러 없음
- [ ] `http://localhost:8000` → `/login` 으로 리다이렉트 확인
- [ ] Google 로그인 버튼 클릭 → Google 인증 화면 이동 확인
- [ ] 로그인 완료 후 대시보드 진입 확인
- [ ] 사이드바에 본인 이름 / 아바타 표시 확인
- [ ] 로그아웃 버튼 클릭 → `/login` 으로 이동 확인
- [ ] 위협 목록 / 리스크 게이지 데이터 표시 확인

---

## 5단계 — GitHub 업로드

```bash
git init
git add .
git commit -m "feat: SAYbrand MVP"
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

- [ ] `.env` 파일이 `.gitignore`에 포함되어 있음 확인 (`git status`에 `.env` 미표시)
- [ ] `*.db` 파일이 `.gitignore`에 포함되어 있음 확인
- [ ] GitHub 저장소 생성 (Private 권장)
- [ ] push 완료

> **주의**: `git add .` 전에 `git status`로 `.env`, `*.db`가 없는지 반드시 확인하세요.

---

## 6단계 — Vercel 배포

- [ ] [Vercel](https://vercel.com) → New Project → GitHub 저장소 연결
- [ ] **Settings → Environment Variables** 에 아래 키 모두 등록
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
  - `GOOGLE_REDIRECT_URI` → `https://<your-domain>.vercel.app/auth/callback`
  - `SESSION_SECRET_KEY`
  - `POLAR_ACCESS_TOKEN`
  - `POLAR_WEBHOOK_SECRET`
  - `POLAR_PRODUCT_ID`
  - `ANTHROPIC_API_KEY` (선택)
  - `GEMINI_API_KEY` (선택)
- [ ] `vercel deploy` 또는 GitHub push → 자동 배포 확인
- [ ] 배포된 URL에서 로그인 동작 확인
- [ ] Google OAuth 앱에 Vercel 도메인 리다이렉션 URI 추가 (1단계로 돌아가서)
- [ ] Polar.sh Webhook URL을 Vercel 도메인으로 업데이트 (2단계로 돌아가서)

---

## 빠른 확인 명령어

```bash
# SESSION_SECRET_KEY 랜덤 생성
python -c "import secrets; print(secrets.token_hex(32))"

# .env가 git에 올라가는지 확인
git status | grep .env    # 아무것도 안 나와야 정상

# 로컬 서버 실행
uvicorn main:app --reload --port 8000
```
