SAYbrand 기술 문서
==================

**SAYbrand** — AI 기반 브랜드 위협 모니터링 SaaS

.. image:: https://img.shields.io/badge/version-v0.3.1-blue
   :alt: version

.. image:: https://img.shields.io/badge/python-3.11+-green
   :alt: python

.. image:: https://img.shields.io/badge/FastAPI-0.115-009688
   :alt: fastapi

----

**SAYbrand**는 공개 SNS 데이터를 3계층 AI 파이프라인으로 실시간 분석하여
브랜드 사칭·가짜뉴스·조직적 봇 공격을 자동 탐지하는 **B2B 브랜드 보호 SaaS**입니다.

.. admonition:: 핵심 차별점

   - L1($0) → L2(저비용) → L3(고위협만) 순서로 AI 비용 최소화
   - 봇·조직적 공격 vs 실제 소비자 불만 자동 구분
   - 한국어 커뮤니티어·초성·반어법 특화 처리
   - AI가 즉시 사용 가능한 PR 대응 문구 3가지 자동 생성

.. toctree::
   :maxdepth: 2
   :caption: 제품 개요

   overview

.. toctree::
   :maxdepth: 3
   :caption: 기술 아키텍처

   architecture
   ai_pipeline
   risk_scoring

.. toctree::
   :maxdepth: 2
   :caption: 기능 상세

   collectors
   reports
   organization
   card_news

.. toctree::
   :maxdepth: 2
   :caption: API 레퍼런스

   api_reference

.. toctree::
   :maxdepth: 2
   :caption: 배포 & 운영

   deployment
   database

Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
