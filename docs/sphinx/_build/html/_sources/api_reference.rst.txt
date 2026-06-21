API 레퍼런스
============

인증
----

모든 ``/api/*`` 엔드포인트는 ``Authorization: Bearer <JWT>`` 헤더 또는
세션 쿠키 필요.

대시보드 ``/api/dashboard``
----------------------------

.. list-table::
   :widths: 40 15 45
   :header-rows: 1

   * - 엔드포인트
     - 메서드
     - 설명
   * - ``/api/dashboard/threats``
     - GET
     - 위협 목록 (필터·정렬·페이지)
   * - ``/api/dashboard/threats/{id}``
     - GET
     - 위협 상세
   * - ``/api/dashboard/threats/{id}``
     - PATCH
     - 상태 변경 (active/dismissed/resolved)
   * - ``/api/dashboard/scan``
     - POST
     - 스캔 실행 (Vercel→Celery / 로컬→직접)
   * - ``/api/dashboard/scan-local``
     - POST
     - 로컬 전용 직접 스캔
   * - ``/api/dashboard/stats``
     - GET
     - 통계 (severity별·platform별)
   * - ``/api/dashboard/version``
     - GET
     - 서비스 버전 (v0.3.1)

보고서 ``/api/reports``
------------------------

.. list-table::
   :widths: 45 15 40
   :header-rows: 1

   * - 엔드포인트
     - 메서드
     - 설명
   * - ``/api/reports/{period}``
     - GET
     - JSON 리포트 (daily/weekly/monthly)
   * - ``/api/reports/{period}/pdf``
     - GET
     - PDF 보고서 다운로드 (A4, 8섹션)
   * - ``/api/reports/{period}/pptx``
     - GET
     - PPT 보고서 다운로드 (16:9, 6슬라이드)
   * - ``/api/reports/threat-map``
     - GET
     - 플랫폼별 위협 인텔리전스 맵
   * - ``/api/reports/archives``
     - GET
     - 조치 완료 아카이브 목록

인증 ``/auth``
--------------

.. list-table::
   :widths: 35 15 50
   :header-rows: 1

   * - 엔드포인트
     - 메서드
     - 설명
   * - ``/auth/google``
     - GET
     - Google OAuth 시작
   * - ``/auth/callback``
     - GET
     - OAuth 콜백, JWT 발급
   * - ``/auth/logout``
     - GET
     - 세션 종료
   * - ``/auth/me``
     - GET
     - 현재 사용자 정보

조직 ``/api/orgs``
-------------------

.. list-table::
   :widths: 45 15 40
   :header-rows: 1

   * - 엔드포인트
     - 메서드
     - 설명
   * - ``/api/orgs``
     - POST
     - 조직 생성
   * - ``/api/orgs/{id}/join``
     - POST
     - 초대코드로 참여
   * - ``/api/orgs/{id}/members``
     - GET
     - 멤버 목록
   * - ``/api/orgs/{id}/members/{uid}``
     - PATCH
     - 멤버 역할·상태 변경
   * - ``/api/orgs/{id}/invite-codes``
     - GET
     - 초대 코드 조회 (역할별 최신 1개)
   * - ``/api/orgs/{id}/pending``
     - GET
     - 승인 대기 목록

결제 ``/billing``
------------------

.. list-table::
   :widths: 40 15 45
   :header-rows: 1

   * - 엔드포인트
     - 메서드
     - 설명
   * - ``/billing/checkout/{plan}``
     - GET
     - Polar 체크아웃 링크 리다이렉트
   * - ``/billing/webhook``
     - POST
     - Polar Svix 웹훅 (서명 검증)
   * - ``/billing/sync``
     - POST
     - 이메일 기준 구독 수동 동기화

기타
----

.. list-table::
   :widths: 45 15 40
   :header-rows: 1

   * - 엔드포인트
     - 메서드
     - 설명
   * - ``/api/keywords``
     - GET/POST/DELETE
     - 모니터링 키워드 관리
   * - ``/api/profile``
     - GET/POST/PATCH
     - 브랜드 프로파일 CRUD
   * - ``/api/support``
     - GET/POST
     - 고객센터 티켓
   * - ``/api/assistant/chat``
     - POST
     - AI 어시스턴트 채팅
   * - ``/api/activity``
     - GET
     - 활동 로그
   * - ``/api/competitor-keywords``
     - GET/POST/DELETE
     - 경쟁사 키워드 관리
