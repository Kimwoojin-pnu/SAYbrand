보고서 시스템
=============

PDF 보고서 (ReportLab)
-----------------------

**엔드포인트:** ``GET /api/reports/{period}/pdf``

**구성 (A4, 8섹션):**

.. list-table::
   :widths: 10 30 60
   :header-rows: 1

   * - 섹션
     - 제목
     - 내용
   * - 표지
     - Cover
     - 브랜드명·기간·브랜드 이미지 점수·KPI 6개
   * - 1
     - 핵심 요약
     - Executive Summary KPI 테이블
   * - 2
     - 위협 현황
     - 심각도별·플랫폼별·위협 유형 Top5 바 차트
   * - 3
     - 감성·감정
     - 긍정/중립/부정 분포·감정 분류·부정 언급 사례
   * - 4
     - 조직 공격·봇
     - 조직적 공격 건수·플랫폼별 감성 분포
   * - 5
     - 미해결 위협 Top 10
     - 카드 형태 (계정·위험도·AI 권고)
   * - 6
     - 조치 완료 내역
     - 실제 해결 위협 목록·메모
   * - 7
     - 모니터링 현황
     - 키워드·플랫폼·분석 엔진 정보
   * - 8
     - 대응 권고사항
     - 위협 등급 기반 구체 권고 + AI 권고

**기술 특징:**

- 한국어 폰트: ``backend/fonts/NanumGothic.ttf`` 번들 (자동 탐색)
- 모든 테이블 너비: **180mm** (A4 210mm - 좌우 마진 각 15mm)
- ``wordWrap='CJK'`` 적용으로 한국어 텍스트 오버플로 방지
- 헤더·푸터 자동 삽입 (표지 제외)

PPT 보고서 (python-pptx)
-------------------------

**엔드포인트:** ``GET /api/reports/{period}/pptx``

**구성 (16:9, 6슬라이드):**

.. list-table::
   :widths: 10 90
   :header-rows: 1

   * - 슬라이드
     - 내용
   * - 1
     - Cover — 브랜드명·기간·KPI 4개 박스 (NAVY 배경)
   * - 2
     - 핵심 요약 — KPI 6개 그리드 + 브랜드 이미지 점수
   * - 3
     - 위협 현황 — 심각도별·플랫폼별 인라인 바 차트
   * - 4
     - 감성 분석 — 감성 분포 + 감정 분류 바 차트
   * - 5
     - 미해결 Top 5 — 테이블 형태 위협 목록
   * - 6
     - 권고사항 — 색상 헤더 권고 카드

보고서 데이터 구성
------------------

.. code-block:: python

   # generate_report() 반환 구조
   {
     "label": "2026년 06월 월간 보고서",
     "period": "2026-05-21 ~ 2026-06-20",
     "summary": {
       "total_threats": 42,
       "unresolved_count": 15,
       "resolved_count": 20,
       "negative_mentions": 18,
       "brand_score": 57.1,          # 0–100
       "false_positive_count": 7,
       "real_resolved_count": 13,
       "organized_count": 3,
       "bot_count": 5,
     },
     "by_severity": {"critical": 2, "high": 8, "medium": 20, "low": 12},
     "by_platform": {"naver": 18, "youtube": 12, "x": 12},
     "by_sentiment": {"negative": 18, "neutral": 15, "positive": 9},
     "by_emotion": {"분노": 10, "혐오": 5, "슬픔": 3, ...},
     "unresolved_threats": [...],    # Top 10, risk_score 내림차순
     "ai_suggestions": [...],        # ai_response_suggestion 있는 Top 3
     "is_mock": False,               # 실데이터 여부
   }
