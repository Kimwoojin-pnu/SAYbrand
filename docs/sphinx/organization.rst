조직 관리 시스템
================

구독 티어별 제한
----------------

.. list-table::
   :widths: 20 20 60
   :header-rows: 1

   * - 티어
     - 조직 수
     - 설명
   * - free
     - 1개
     - 기본 무료
   * - starter
     - 3개
     - 스타터 플랜
   * - pro
     - 5개
     - 프로 플랜
   * - enterprise
     - 무제한
     - 엔터프라이즈

멤버 역할 (RBAC)
-----------------

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - 역할
     - 권한
   * - owner
     - 전체 관리 (삭제 포함)
   * - admin
     - 멤버 관리·설정 변경
   * - member
     - 스캔·위협 처리 가능
   * - viewer
     - 읽기 전용

가입 플로우
-----------

**방법 1 — 초대 코드:**

.. code-block:: text

   관리자 → 코드 생성 (역할 지정·만료일·사용 횟수)
   → URL 공유 → 사용자 코드 입력 → 즉시 active

**방법 2 — 승인 요청:**

.. code-block:: text

   사용자 → 참여 신청 (status: pending)
   → 관리자 승인 (active) / 거절 (DB 레코드 삭제)

온보딩 3단계
------------

``/onboarding`` — CustomerProfile 없으면 자동 리다이렉트

.. code-block:: text

   Step 1 — 경로 선택
     ├ 새 조직 만들기 → Step 2A (조직 이름·도메인)
     └ 기존 조직 참여 → Step 2B (초대 코드 입력)

   Step 3 — 브랜드 등록
     ├ 브랜드명 + 별칭 (공식·영문·약칭·별명)
     ├ 업종 선택 (뷰티/패션/식품/IT/금융/기타)
     ├ 공식 SNS 계정 등록
     ├ 임직원 등록 (CEO·임원·직원, 우선순위 차등)
     └ 모니터링 키워드 추가

화이트라벨 지원
---------------

.. code-block:: python

   # Organization 테이블 필드
   white_label_enabled: bool
   white_label_logo_url: str       # 커스텀 로고
   white_label_brand_name: str     # 커스텀 브랜드명
   white_label_color: str          # #RRGGBB 테마 색상
