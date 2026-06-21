카드뉴스 자동 생성 파이프라인
================================

SAYbrand가 탐지한 브랜드 위협 데이터를 자동으로 유튜브 쇼츠용 카드뉴스 영상으로 변환하는 독립 파이프라인.

위치: ``card-news-pipeline/``

전체 흐름
---------

.. code-block:: text

   [PostgreSQL 위협 DB]
       │ db_source.py — 최근 14일, critical/high/medium, 최신순 LIMIT 100
       ▼
   [selector.py — 소재 선택]
       │ 오늘 데이터 우선 → 1일 전 → 2일 전 → 3일 전 → 전체 최고점
       ▼
   [llm_scripter.py — 스크립트 생성]
       │ Claude Haiku 4.5 (API 키 없을 때 템플릿 폴백)
       │ 1슬라이드, headline ≤ 20자, body ≤ 150자, 태그 5개
       ▼
   [renderer.py — 슬라이드 렌더링]
       │ Playwright Chromium, 1080×1920 (쇼츠 세로형 규격)
       │ Pixazo API로 히어로 이미지 생성 (없으면 플레이스홀더)
       ▼
   [video.py — 영상 조립]
       │ FFmpeg — 슬라이드 PNG → MP4, assets/bgm/*.mp3 믹싱
       ▼
   [discord_review.py — 검수 요청]
       │ Discord Webhook 전송, review_status.json 저장
       ▼
   [youtube_upload.py — YouTube 업로드]
       └ OAuth2 Refresh Token, 비공개(private), #Shorts 태그 자동 추가

모듈별 역할
-----------

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - 모듈
     - 역할
   * - ``db_source.py``
     - PostgreSQL 쿼리 / 환경변수 없으면 mock_data 폴백
   * - ``selector.py``
     - 오늘 날짜 우선 후보 선택, used_ids 중복 제거
   * - ``llm_scripter.py``
     - Claude Haiku 4.5 JSON 스크립트 생성
   * - ``scripter.py``
     - LLM 실패 시 규칙 기반 템플릿 스크립트
   * - ``renderer.py``
     - Playwright로 HTML → PNG 슬라이드 렌더링
   * - ``slide_template.py``
     - 슬라이드 HTML 템플릿 빌더
   * - ``pixazo_image_generator.py``
     - Pixazo API 히어로 이미지 생성
   * - ``video.py``
     - FFmpeg MP4 조립 + BGM 믹싱
   * - ``orchestrator.py``
     - 전체 파이프라인 조율 + Discord 검수 요청
   * - ``discord_review.py``
     - Discord Webhook 검수 메시지 전송
   * - ``review_status.py``
     - 검수 상태 JSON 저장/읽기
   * - ``youtube_upload.py``
     - YouTube Data API v3 업로드
   * - ``alerts.py``
     - 파이프라인 오류 알림
   * - ``run_log.py``
     - 실행 이력 로깅
   * - ``store.py``
     - used_ids 영속화 (중복 방지)

DB 쿼리
-------

.. code-block:: sql

   SELECT id::text,
          COALESCE(threat_type, severity, '위협') AS category,
          COALESCE(
              NULLIF(CASE WHEN ai_analysis LIKE '[Mock]%' THEN NULL
                          ELSE ai_analysis END, ''),
              content_preview
          ) AS summary,
          risk_score::int,
          detected_at::date
   FROM threats
   WHERE content_preview IS NOT NULL
     AND detected_at >= NOW() - INTERVAL '14 days'
     AND severity IN ('critical', 'high', 'medium')
   ORDER BY detected_at DESC NULLS LAST, risk_score DESC NULLS LAST
   LIMIT 100

- Mock AI 분석(``[Mock]`` 접두어)은 ``content_preview`` 로 대체
- 최신순 정렬 후 위험도 내림차순 — 오늘 데이터가 항상 먼저 로드됨

소재 선택 알고리즘
------------------

.. code-block:: python

   # selector.py
   for days_back in [0, 1, 2, 3]:
       pool = [r for r in candidates if r.detected_at == today - timedelta(days=days_back)]
       if pool:
           return max(pool, key=lambda r: r.impact_score)

   # 최근 3일 내 없으면 전체 최고점
   return max(candidates, key=lambda r: r.impact_score)

LLM 스크립트 생성
-----------------

Claude Haiku 4.5가 아래 JSON 형식으로 스크립트를 생성합니다.

.. code-block:: json

   {
     "title": "카드뉴스 제목",
     "slides": [
       {"headline": "20자 이내 헤드라인", "body": "150자 이내 본문"}
     ],
     "description": "유튜브 설명문",
     "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"]
   }

API 키 없을 때는 ``scripter.py`` 의 규칙 기반 템플릿으로 자동 폴백.

YouTube 업로드
--------------

.. code-block:: python

   # youtube_upload.py — 비공개 업로드
   body = {
       "snippet": {
           "title": status.title,
           "description": status.description + "\n\n#Shorts",
           "tags": status.tags + ["Shorts"],
           "categoryId": "25",          # News & Politics
       },
       "status": {"privacyStatus": "private"},
   }

OAuth2 Refresh Token 방식. ``youtube_auth_setup.py`` 스크립트로 토큰 발급.

환경 변수
---------

.. code-block:: ini

   DATABASE_URL=postgresql://...        # 위협 DB (없으면 mock)
   ANTHROPIC_API_KEY=sk-ant-...         # Claude Haiku (없으면 템플릿 폴백)
   DISCORD_WEBHOOK_URL=https://...      # 검수 요청 (없으면 생략)
   YOUTUBE_CLIENT_ID=...
   YOUTUBE_CLIENT_SECRET=...
   YOUTUBE_REFRESH_TOKEN=...            # youtube_auth_setup.py로 발급

실행 및 테스트
--------------

.. code-block:: bash

   cd card-news-pipeline
   pip install -r requirements.txt
   python run.py

   # 테스트 (93 passed, 2026-06-21 기준)
   pytest tests/ -v
