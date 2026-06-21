데이터 수집기
=============

**디렉토리:** ``backend/services/collectors/``

수집기 구현 상태
----------------

.. list-table::
   :widths: 25 15 20 40
   :header-rows: 1

   * - 수집기
     - 상태
     - API/방식
     - 비고
   * - ``naver.py``
     - ✅ 실동작
     - Naver Search API
     - 25건 수집·3건 위협 분류 검증 완료
   * - ``youtube.py``
     - ✅ 키 있을 때
     - YouTube Data API v3
     - remove_pii 적용
   * - ``x_twitter.py``
     - ✅ 키 있을 때
     - X API v2 Bearer Token
     - remove_pii 적용
   * - ``community_kr.py``
     - 🟡 Mock
     - 크롤링
     - 에펨·더쿠·클리앙·루리웹·인스티즈
   * - Instagram
     - ❌ v1.1
     - Meta API
     - 접근 제한으로 보류
   * - TikTok
     - ❌ v1.1
     - TikTok API
     - 접근 제한으로 보류

컴플라이언스 처리
-----------------

**파일:** ``backend/services/collectors/compliance.py``

- **robots.txt 자동 체크**: 수집 전 허용 여부 확인
- **PII 마스킹** (``remove_pii()``): 전화번호·이메일·주민번호 정규식 비식별화
- **Rate Limiter**: 요청 간 최소 2초 지연
- **뉴스 도메인 분류**: ``is_news_domain()``으로 언론사 구분

Orchestrator
------------

**파일:** ``backend/services/collectors/orchestrator.py``

.. code-block:: python

   # 전체 브랜드 프로파일 병렬 수집
   await orchestrator.collect_all_profiles(db)

   # 단일 프로파일 즉시 수집
   await orchestrator.collect_single_profile(profile_id, db)

RawPost 공통 데이터 구조
------------------------

.. code-block:: python

   {
       "platform": "naver",
       "source_account": "blog.naver.com/user123",
       "source_url": "https://...",
       "content": "본문 텍스트 (PII 마스킹 완료)",
       "published_at": "2026-06-20T10:00:00",
       "reach_estimate": 1500,       # 추정 도달 수
       "is_mock": False,
   }
