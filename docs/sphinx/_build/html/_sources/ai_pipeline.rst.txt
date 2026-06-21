AI 분석 파이프라인
==================

3계층 설계 원칙
---------------

.. code-block:: text

   비용 = f(처리량)이므로, 필터링 순서로 비용 최소화:

   L1 — 규칙 기반 ($0)        : 전체 수집량의 ~80% 탈락
   L2 — AI 감성 분석 (저비용)  : L1 통과분의 ~85% 처리
   L3 — 심층 대응 (고비용)     : L2에서 score ≥ 0.85인 케이스만

L1 — 규칙 기반 필터
-------------------

**파일:** ``backend/services/analyzers/l1_filter.py``

- 키워드 데이터베이스 900개+ (18개 카테고리)
- ``CRITICAL_BYPASS``: 법적 위협 패턴 → 즉시 score=1.0, severity="critical"
- ``NEGATIVE_FILTERS`` 20개+: 범용어·중립 단어 오탐 방지
- ``score < 0.05`` → 탈락 (비용 $0)
- 업종별 임계값: ``0.08 / risk_multiplier`` (예: 식품업 0.067)

.. code-block:: python

   result = l1_filter(text, brand_keywords=["삼성", "Samsung", "갤럭시"])
   # {'pass': True, 'score': 0.73, 'severity': 'high',
   #  'auto_critical': False, 'matched_categories': ['B4_organized_attack_bot']}

L1 카테고리 매핑 (18개)
~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - 카테고리 코드
     - 설명
   * - A1_impersonation_account
     - 계정 사칭
   * - A2_ceo_impersonation
     - CEO 사칭
   * - A3_product_counterfeit
     - 위조품·가품 유통
   * - A4_logo_visual_abuse
     - 로고 무단 사용
   * - B1_product_safety_crisis
     - 제품 안전 위기
   * - B2_legal_crisis
     - 법적 위기
   * - B3_financial_crisis
     - 재무 위기
   * - B4_organized_attack_bot
     - 조직적 봇 공격
   * - B5_consumer_complaint_high
     - 고강도 소비자 불만
   * - B6_consumer_complaint_mid
     - 중강도 소비자 불만
   * - B7_fake_news_patterns
     - 가짜뉴스 패턴
   * - B8_crisis_escalation
     - 위기 확산
   * - B9_competitor_attack
     - 경쟁사 공격
   * - C1_executive_misconduct
     - 임직원 비위
   * - C2_internal_leak
     - 내부 정보 유출
   * - C3_labor_issue
     - 노동 이슈
   * - KR_community_slang
     - 한국 커뮤니티 은어
   * - KR_sns_attack_patterns
     - SNS 조직적 공격 패턴

L2 — AI 감성·의도 분석
-----------------------

**파일:** ``backend/services/analyzers/l2_text.py``

폴백 체인
~~~~~~~~~

.. code-block:: text

   HyperCLOVA X  (HYPERCLOVA_API_KEY 있을 때)
       ↓ 실패
   Gemini 2.5 Flash Lite  (GEMINI_API_KEY, 유료 전환 완료)
       ↓ 실패
   KNU 한국어 감성 사전  (14,854개 단어, 오프라인 항상 동작)

한국어 특화 처리
~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - 패턴
     - 설명
   * - 반어법
     - "ㄹㅇ 대박이네", "쩐다" → 문맥 기반 부정 판별
   * - 초성 줄임말
     - ㄷㄷ(두려움), ㅂㄷ(분노), ㄱㄱ(공유 유도=봇 신호)
   * - 커뮤니티어
     - "각"(~할 것 같다), "레전드"(극단적 사건), "박제"(증거 수집)
   * - 봇 패턴
     - "공유하면~", "rt하면~", "긴급·속보" 위장, 제보 형식 위장

12개 마케팅 위기 카테고리
~~~~~~~~~~~~~~~~~~~~~~~~~

불매운동 / 캠페인역풍 / 경쟁사공격 / ESG위반제보 / 갑질폭로 /
제품결함확산 / 허위정보유포 / 브랜드사칭 / 주가영향루머 /
채용이슈 / 파트너십위기 / 위기확산

배치 처리
~~~~~~~~~

.. code-block:: python

   # 10건 배치로 API 호출 비용 최소화
   results = await analyze_batch(posts, profile_id=1, db=db)

L3 — 심층 대응 분석
--------------------

**파일:** ``backend/services/analyzers/l3_deep.py``

**호출 조건:** ``risk_score ≥ 85`` (고위협 케이스만)

폴백 체인
~~~~~~~~~

.. code-block:: text

   Gemini 2.5 Flash Lite  (기본)
       ↓ 실패
   Claude Haiku 4.5  (ANTHROPIC_API_KEY)

출력 필드
~~~~~~~~~

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - 필드
     - 설명
   * - ``brand_damage_type``
     - 매출타격 / 채용악영향 / 파트너십위험 / 주가영향 / 이미지실추 / 없음
   * - ``communication_urgency``
     - 즉시(1시간내) / 당일(24시간) / 48시간내 / 모니터링
   * - ``is_false_positive``
     - true이면 오탐 처리
   * - ``is_organized_attack``
     - true이면 조직적 공격
   * - ``legal_action_required``
     - true이면 법적 대응 필요
   * - ``response_suggestion``
     - SNS 대응 / 공식 채널 대응 / 내부 조치 (3가지 구체 문구)

조직적 공격 탐지
----------------

**파일:** ``backend/services/risk_scorer.py`` → ``calculate_attack_score()``

.. list-table::
   :widths: 30 45 25
   :header-rows: 1

   * - 컴포넌트
     - 의미
     - 가중치
   * - text_uniformity
     - 텍스트 동일성 (1 - 분산)
     - 0.25
   * - account_cluster
     - 공격 계정 간 맞팔 비율
     - 0.20
   * - account_quality_inverse
     - 계정 품질 낮을수록 ↑
     - 0.20
   * - temporal_cluster
     - 게시 시각 60분 내 집중도
     - 0.15
   * - cross_platform
     - 플랫폼 간 시간차 < 1시간
     - 0.10
   * - reaction_uniformity
     - 반응 다양성 낮을수록 ↑
     - 0.10

판정 기준:

- ``attack_score ≥ 0.7`` → **organized_attack** (조직적 공격)
- ``attack_score 0.4–0.7`` → **gray_zone** (회색지대)
- ``attack_score < 0.4`` → **legitimate_criticism** (정당한 비판)
