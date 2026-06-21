배포 & 운영
===========

듀얼 배포 구성
--------------

.. code-block:: text

   Vercel                        Railway
   ────────────────────          ─────────────────────
   FastAPI (app.py)              Celery Worker + Beat
   프론트엔드 HTML                Redis
   JWT 인증·OAuth               PostgreSQL
   PDF/PPT 생성                  30분 주기 자동 수집

.. important::
   Vercel 진입점은 ``app.py`` 입니다.
   ``main.py`` 수정은 Vercel에 반영되지 않습니다.

Vercel 주의사항
---------------

.. code-block:: python

   # 로깅: print()만 Vercel 로그에 표시
   print(f"[SCAN] 결과: {result}")   # ✅ Vercel 로그에 표시
   logging.info("...")               # ❌ Vercel에서 미표시

   # lifespan 이벤트 미작동
   # DB 마이그레이션은 Railway PostgreSQL에서 직접 SQL 실행

   # datetime: naive UTC 필수
   datetime.utcnow()              # ✅
   datetime.now(timezone.utc)    # ❌ asyncpg DataError 발생

Railway 설정
------------

.. code-block:: toml

   # railway.toml
   [deploy]
   startCommand = "celery -A backend.workers.celery_app worker -B -c 2"

환경 변수 목록
--------------

.. code-block:: ini

   # 데이터베이스
   DATABASE_URL=postgresql+asyncpg://user:pass@host/db

   # AI API
   ANTHROPIC_API_KEY=sk-ant-...          # Claude Haiku 4.5 (L3)
   GEMINI_API_KEY=...                    # Gemini 2.5 Flash Lite (L2)
   GOOGLE_VISION_API_KEY=...            # Vision API
   HYPERCLOVA_API_KEY=...               # HyperCLOVA X (L2 기본)
   HYPERCLOVA_GATEWAY_KEY=...

   # SNS 수집
   NAVER_CLIENT_ID=...
   NAVER_CLIENT_SECRET=...
   YOUTUBE_API_KEY=...
   X_BEARER_TOKEN=...

   # OAuth
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   SECRET_KEY=...                        # JWT 서명 키

   # 결제 (Polar)
   POLAR_CHECKOUT_LINK_STARTER=https://...
   POLAR_CHECKOUT_LINK_PRO=https://...
   POLAR_WEBHOOK_SECRET=whsec_...

   # 알림
   SLACK_WEBHOOK_URL=https://hooks.slack.com/...
   SUPPORT_ADMIN_EMAILS=admin@example.com

   # Redis / Celery
   REDIS_URL=redis://...
   CELERY_BROKER_URL=redis://...

로컬 개발 환경
--------------

.. code-block:: bash

   # 서버 기동
   python -m uvicorn main:app --reload

   # DB 초기화
   Get-Process python | Stop-Process -Force   # (Windows)
   Remove-Item brandguard.db

   # Docker 전체 스택
   docker-compose up

Polar 결제 Svix 웹훅 서명 검증
--------------------------------

.. code-block:: python

   # whsec_ prefix 제거 후 base64 decode
   # 헤더 형식: v1,<base64_sig>  (쉼표, hex 아님)
   # httpx 호출 시 follow_redirects=True 필수 (307 방지)
