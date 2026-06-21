시스템 아키텍처
===============

기술 스택
---------

.. code-block:: text

   Backend:   FastAPI 0.115 + SQLAlchemy 2.0 async (Python 3.11+)
   Frontend:  Tailwind CSS (CDN) + Vanilla JS (빌드 없음)
   Database:  SQLite (로컬) / PostgreSQL+asyncpg (Railway 운영)
   Cache:     Redis 5.0+ + Celery 5.4
   AI L2:     Gemini 2.5 Flash Lite  (google-genai ≥ 1.0.0)
   AI L3:     Claude Haiku 4.5       (anthropic ≥ 0.50.0)
   이미지:    imagehash 4.3.2 (pHash 해밍 거리)
   보고서:    ReportLab ≥ 4.0 (PDF) · python-pptx ≥ 0.6.21 (PPT)
   배포:      Vercel (API + 프론트) + Railway (Celery 워커)
   인증:      Google OAuth 2.0 (Authlib)
   결제:      Polar (체크아웃 링크 + Svix 웹훅)
   알림:      Slack Webhook (slack-sdk ≥ 3.27.0)

전체 데이터 흐름
----------------

.. code-block:: text

   [SNS 플랫폼]
       │  YouTube API · Naver Search API · X Bearer Token
       ▼
   [수집기 Orchestrator]  ← Celery Beat 30분 주기
       │
       ▼
   [L1 규칙 기반 필터]  ($0 비용)
       │ score < 0.05 → 버림
       │ 통과
       ▼
   [Entity Resolver]  ← 브랜드 프로파일 / 공식 계정 목록
       │
       ▼
   [L2 텍스트 분석]  ← HyperCLOVA → Gemini → KNU 감성 사전
       │ score < 0.85 → DB 저장 (severity: low/medium)
       │ score ≥ 0.85 → L3 호출
       ▼
   [L3 심층 분석]  ← Gemini 2.5 Flash Lite → Claude Haiku 4.5 (폴백)
       │
       ▼
   [리스크 스코어링 엔진]  → risk_score 0–100 산출
       │
       ▼
   [PostgreSQL DB]
       │
       ├──→ [대시보드 API]   → 프론트엔드 실시간 표시
       ├──→ [Slack 알림]     ← Critical 즉시 발송
       └──→ [PDF / PPT 보고서] ← 일간·주간·월간

프론트엔드 페이지 구성
----------------------

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - URL
     - 설명
   * - ``/``
     - 마케팅 랜딩 페이지
   * - ``/products``
     - 5개 기능 탭 통합 소개
   * - ``/login``
     - Google OAuth 로그인
   * - ``/onboarding``
     - 3단계 온보딩 (경로선택→조직설정→브랜드등록)
   * - ``/dashboard``
     - 메인 대시보드 (게이지·KPI·위협 목록)
   * - ``/threats``
     - 위협 상세 목록 (필터·정렬·AI 재분석)
   * - ``/actions``
     - 처리 대기 위협 큐
   * - ``/brand-image``
     - 브랜드 이미지 점수 추이
   * - ``/negative-mentions``
     - 부정 언급 피드백
   * - ``/reports``
     - 보고서 (일간·주간·월간 + PDF/PPT 다운로드)
   * - ``/history``
     - 처리 내역 + 90일 아카이브
   * - ``/settings``
     - 키워드·프로파일·알림·구독 설정
   * - ``/support``
     - 고객센터 게시판
   * - ``/orgs/new``
     - 조직 생성
   * - ``/orgs/join``
     - 초대 코드로 조직 참여

디자인 시스템
-------------

.. code-block:: css

   /* 폰트 */
   영문 display:  Syne           (font-display)
   한글 본문:     Noto Sans KR   (font-body)
   코드/수치:     JetBrains Mono (font-mono)

   /* 색상 토큰 */
   brand-navy:   #0c1428
   brand-blue:   #1a6ef8
   critical:     #dc2626
   high:         #ea580c
   medium:       #d97706
   low:          #16a34a

   /* 다크모드 (기본 dark) */
   localStorage('db-theme') = 'dark' | 'light'
   html[data-theme="dark"] 속성으로 전환

비동기 워커 (Celery)
---------------------

.. list-table::
   :widths: 35 20 45
   :header-rows: 1

   * - 태스크
     - 주기
     - 설명
   * - ``collect_all_profiles``
     - 30분
     - 전 플랫폼 병렬 수집
   * - ``send_daily_reports``
     - 매일 09:00 KST
     - 일간 보고서 이메일
   * - ``send_weekly_reports``
     - 매주 월요일
     - 주간 보고서 이메일
   * - ``purge_expired_data``
     - 매일 02:00
     - 90일 경과 아카이브 삭제

.. code-block:: bash

   # Railway 운영 환경 (railway.toml)
   celery -A backend.workers.celery_app worker -B -c 2

   # 로컬 개발
   docker-compose up   # postgres + redis + worker + flower
