리스크 스코어링 엔진
====================

**파일:** ``backend/services/risk_scorer.py``

점수 계산 공식
--------------

.. code-block:: python

   base = (
       SEVERITY_WEIGHTS[severity]       # 심각도 가중치
       × MODULE_WEIGHTS[module]         # 모듈 가중치
       × PLATFORM_WEIGHTS[platform]     # 플랫폼 가중치
       × confidence                     # AI 신뢰도 0.0–1.0
       × 100
   )
   base *= industry_config["risk_multiplier"]  # 업종 가중치
   if is_organized: base = min(base * 1.3, 100)
   final = base × (recency_weight + velocity_bonus)
   risk_score = clamp(round(final), 0, 100)

가중치 테이블
-------------

.. list-table::
   :widths: 25 25 50
   :header-rows: 1

   * - 구분
     - 항목
     - 가중치
   * - 심각도
     - critical / high / medium / low
     - 1.0 / 0.7 / 0.4 / 0.15
   * - 모듈
     - A(사칭) / B(루머) / C(임직원)
     - 1.0 / 0.85 / 0.7
   * - 플랫폼
     - Instagram / YouTube / TikTok / X / Naver
     - 1.0 / 0.9 / 0.85 / 0.8 / 0.7

최신성 가중치 (recency_weight)
-------------------------------

.. list-table::
   :widths: 40 60
   :header-rows: 1

   * - 경과 시간
     - 가중치
   * - < 1시간
     - 1.0
   * - 1–6시간
     - 0.9
   * - 6–24시간
     - 0.75
   * - 1–3일
     - 0.5
   * - 3–7일
     - 0.3
   * - 7일 초과
     - 0.1

확산 속도 보너스 (velocity_bonus)
----------------------------------

.. code-block:: python

   velocity_bonus = min(engagements_per_hour / 1000, 0.3)
   # 시간당 1,000 인게이지먼트 → +0.3 보너스

전체 브랜드 점수 (Overall Score)
----------------------------------

.. code-block:: text

   Overall = Module_A × 0.40 + Module_B × 0.35 + Module_C × 0.25

   임계값:
     80–100 → CRITICAL  즉각 Slack 알림
     60–79  → HIGH      당일 대응
     35–59  → MEDIUM    모니터링
     0–34   → LOW       정기 리포트

업종별 알림 임계값
-------------------

.. code-block:: python

   # 금융업은 45점 이상이면 high, 일반업은 60점 이상
   threshold = profile.industry_config.get("alert_threshold", 60)

   if risk_score >= 80:   return "critical"
   if risk_score >= threshold: return "high"
   if risk_score >= 35:   return "medium"
   return "low"
