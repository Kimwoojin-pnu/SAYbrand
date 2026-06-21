데이터베이스 스키마
===================

주요 테이블 (SQLAlchemy 2.0 ORM)
----------------------------------

threats — 위협 정보 (핵심)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   id, user_id, org_id
   module          : A(사칭) / B(루머) / C(임직원)
   threat_type     : account_impersonation / organized_rumor / ...
   severity        : critical / high / medium / low / feedback
   platform        : instagram / youtube / x / tiktok / naver
   source_account, source_url, content_preview
   confidence      : 0.0–1.0 (AI 신뢰도)
   risk_score      : 0–100 (리스크 스코어)
   ai_analysis     : L3 분석 텍스트
   ai_response_suggestion : PR 대응 문구
   bot_probability : 0.0–1.0
   is_organized    : bool (조직적 공격 여부)
   sentiment       : positive / neutral / negative
   emotion         : 분노 / 공포 / 혐오 / 슬픔 / 놀람 / 기쁨 / 중립
   sentiment_score : -1.0–1.0
   reach_estimate  : 추정 도달 수
   status          : active / dismissed / resolved
   resolution_type : false_positive / real_resolved
   resolution_method, resolution_note
   detected_at, updated_at

users — 사용자
~~~~~~~~~~~~~~

.. code-block:: text

   id, name, email, company
   user_type           : google
   google_id, avatar_url
   polar_customer_id
   subscription_status : free / active / canceled
   subscription_tier   : free / starter / pro / enterprise
   created_at

organizations — 조직
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   id, name, slug, owner_user_id
   invite_mode         : approval / open
   subscription_tier, subscription_status
   slack_webhook_url
   white_label_enabled, white_label_logo_url
   white_label_brand_name, white_label_color
   created_at

customer_profiles — 브랜드 프로파일
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   id, user_id, org_id
   profile_type  : company / individual
   display_name, industry, description, logo_url
   dart_corp_code, wikidata_id

customer_aliases — 브랜드 별칭
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   id, profile_id
   alias         : 실제 별칭 텍스트
   alias_type    : official / nickname / abbreviation / english
   weight        : 1.0 기본 (L1 필터 가중치)

customer_executives — 임직원 (Module C)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   id, profile_id, name, role
   photo_url
   priority      : 1=CEO / 2=임원 / 3=일반

usage_logs — AI API 비용 추적
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   id, user_id, profile_id
   model         : hyperclova / gemini / claude / mock
   layer         : L2_text / L2_image / L3
   tokens_in, tokens_out, cost_usd
   created_at

archived_threats — 조치 완료 보관함
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   id, original_threat_id
   severity, threat_type, platform
   action_taken, resolution_note
   archived_at
   expires_at    : archived_at + 90일 (자동 삭제)

invite_codes — 초대 코드
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   id, org_id, code (20자 고유)
   role_to_assign, expires_at
   max_uses      : 0 = 무제한
   uses_count, is_active
