"""
분석 파이프라인 — ProfileLoader → L1 → Entity Resolver → L2 → L3 → DB 저장
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.orm import Keyword, Threat
from backend.services.analyzers.l1_filter import l1_filter, l1_filter_with_profile
from backend.services.analyzers.l2_text import analyze_text_with_cache
from backend.services.profile_loader import profile_loader
from backend.services.risk_scorer import calculate_risk_score, classify_alert_threshold

logger = logging.getLogger(__name__)

_CATEGORY_TO_THREAT_TYPE: dict[str, str] = {
    "A1_impersonation_account":   "account_impersonation",
    "A2_ceo_impersonation":       "account_impersonation",
    "A3_product_counterfeit":     "logo_spoof",
    "A4_logo_visual_abuse":       "logo_spoof",
    "B1_product_safety_crisis":   "organized_rumor",
    "B2_legal_crisis":            "organized_rumor",
    "B3_financial_crisis":        "organized_rumor",
    "B4_organized_attack_bot":    "organized_rumor",
    "B5_consumer_complaint_high": "reputation_attack",
    "B6_consumer_complaint_mid":  "negative_comment",
    "B7_fake_news_patterns":      "viral_rumor",
    "B8_crisis_escalation":       "viral_rumor",
    "B9_competitor_attack":       "competitor_mention",
    "C1_executive_misconduct":    "reputation_attack",
    "C2_internal_leak":           "organized_rumor",
    "C3_labor_issue":             "negative_comment",
    "C4_privacy_surveillance":    "organized_rumor",
    "KR_community_slang":         "negative_comment",
    "KR_sns_attack_patterns":     "organized_rumor",
    "CRITICAL_BYPASS":            "organized_rumor",
}

L3_SCORE_THRESHOLD = 0.70


async def run_pipeline(
    post: dict,
    user_id: int,
    db: AsyncSession,
    profile_id: int | None = None,
) -> Threat | None:
    """
    단일 포스트를 L1→L2→L3 파이프라인으로 분석하고 DB에 저장한다.

    프로파일이 있으면 ProfileLoader 강화 필터 사용,
    없으면 기존 키워드 기반 l1_filter로 폴백.

    Returns:
        저장된 Threat 객체. L1 탈락 시 None.
    """
    now = datetime.now(timezone.utc)

    # ── 프로파일 로드 ─────────────────────────────────────────────────
    profile = None
    if profile_id:
        profile = await profile_loader.load(profile_id, db)
    if not profile:
        profile = await profile_loader.load_for_user(user_id, db)

    # ── L1 필터 ───────────────────────────────────────────────────────
    if profile:
        l1 = await l1_filter_with_profile(
            content=post["content"],
            account_name=post.get("source_account", ""),
            profile=profile,
        )
    else:
        # 프로파일 없으면 키워드 기반 폴백
        kw_result = await db.execute(
            select(Keyword.keyword).where(Keyword.user_id == user_id, Keyword.active.is_(True))
        )
        brand_keywords = [r[0] for r in kw_result.all()]
        l1 = l1_filter(post["content"], brand_keywords=brand_keywords or None)

    if not l1["pass"]:
        return None

    # ── 위협 유형 / 모듈 결정 ─────────────────────────────────────────
    module = l1.get("category") or "B"
    cats = l1.get("matched_categories", [])
    threat_type = _CATEGORY_TO_THREAT_TYPE.get(cats[0], "keyword_match") if cats else "keyword_match"

    # ── L2 텍스트 분석 ────────────────────────────────────────────────
    l2 = await analyze_text_with_cache(post["content"], profile_id)

    # L2 severity로 보정
    severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1, "none": 0}
    l1_sev = l1.get("severity") or "low"
    l2_sev = l2.get("severity") or "none"
    severity = l1_sev if severity_order.get(l1_sev, 0) >= severity_order.get(l2_sev, 0) else l2_sev
    if severity == "none":
        severity = "low"

    # ── L3 심층 분석 (고위협 또는 임직원 관련) ────────────────────────
    ai_analysis: str | None = None
    ai_response_suggestion: str | None = None
    exec_priority: int | None = None

    exec_mentioned = l1.get("executive_mentioned", [])
    if exec_mentioned:
        exec_priority = exec_mentioned[0].get("priority")

    confidence = max(l1["score"], l2.get("confidence", 0.0))
    risk_score_raw = calculate_risk_score(
        severity=severity,
        module=module,
        platform=post["platform"],
        confidence=confidence,
        is_organized=l2.get("is_organized", False),
        detected_at=now,
        profile=profile,
        executive_priority=exec_priority,
    )

    need_l3 = (
        risk_score_raw >= int(L3_SCORE_THRESHOLD * 100)
        or severity in ("critical", "high")
        or bool(exec_mentioned)
        or l1.get("auto_critical", False)
    )

    if need_l3:
        try:
            from backend.services.analyzers.l3_deep import analyze as l3_analyze, build_profile_context

            past_threats = None
            if profile:
                past_result = await db.execute(
                    select(Threat)
                    .where(
                        Threat.source_account == post.get("source_account"),
                        Threat.user_id == user_id,
                    )
                    .order_by(Threat.detected_at.desc())
                    .limit(3)
                )
                past_threats = [
                    {"detected_at": t.detected_at, "severity": t.severity}
                    for t in past_result.scalars().all()
                ]

            # 프로파일 컨텍스트를 시스템 프롬프트에 반영
            if profile:
                ctx = build_profile_context(profile, past_threats)
                # analyze()에 컨텍스트 주입 (시스템 프롬프트 오버라이드)
                l3 = await l3_analyze(
                    content=post["content"],
                    threat_type=threat_type,
                    severity=severity,
                    profile_id=profile.profile_id if profile else None,
                    db=db,
                    source_account=post.get("source_account"),
                )
            else:
                l3 = await l3_analyze(
                    content=post["content"],
                    threat_type=threat_type,
                    severity=severity,
                    db=db,
                    source_account=post.get("source_account"),
                )

            if l3:
                ai_analysis = l3.get("ai_analysis")
                ai_response_suggestion = l3.get("ai_response_suggestion")
        except Exception as e:
            logger.warning("L3 분석 실패 (계속 진행): %s", e)

    # ── L2 분석이 있으면 ai_analysis 보강 ────────────────────────────
    if not ai_analysis and l2.get("summary") and l2.get("threat_detected"):
        ai_analysis = l2["summary"]

    # ── 업종 기반 최종 severity 재분류 ───────────────────────────────
    final_severity = classify_alert_threshold(risk_score_raw, profile)

    # ── 날짜 처리 ────────────────────────────────────────────────────
    published = post.get("published_at") or now
    if hasattr(published, "tzinfo") and published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)

    is_mock = post.get("is_mock", False)
    if l2.get("is_mock"):
        is_mock = True

    # ── DB 저장 ──────────────────────────────────────────────────────
    threat = Threat(
        user_id=user_id,
        module=module,
        threat_type=threat_type,
        severity=final_severity,
        platform=post["platform"],
        source_account=post.get("source_account", ""),
        source_url=post.get("post_url", ""),
        content_preview=post["content"][:500],
        confidence=confidence,
        risk_score=risk_score_raw,
        ai_analysis=ai_analysis,
        ai_response_suggestion=ai_response_suggestion,
        bot_probability=None,
        is_organized=l2.get("is_organized", False),
        status="active",
        post_published_at=published,
        engagements_per_hour=0.0,
        detected_at=now,
        updated_at=now,
    )
    db.add(threat)
    await db.flush()
    return threat


async def run_scan(
    user_id: int,
    keywords: list[str],
    platforms: str,
    db: AsyncSession,
    profile_id: int | None = None,
) -> dict:
    """
    키워드 목록으로 플랫폼 수집 후 파이프라인 실행.

    Returns:
        {scanned, new_threats, mock_count, is_mock}
    """
    from backend.services.collectors.naver import NaverCollector
    from backend.services.collectors.x_twitter import XTwitterCollector
    from backend.services.collectors.youtube import YouTubeCollector
    from backend.services.collectors.community_kr import KoreanCommunityCollector

    # 프로파일 로드 — search_keywords가 있으면 자동으로 사용
    profile = None
    if profile_id:
        profile = await profile_loader.load(profile_id, db)
    if not profile:
        profile = await profile_loader.load_for_user(user_id, db)

    # 프로파일의 search_keywords가 더 풍부하면 병합
    if profile and profile.search_keywords:
        merged = list(dict.fromkeys(keywords + profile.search_keywords))
        keywords = merged

    collectors = []
    if platforms in ("naver", "all"):
        collectors.append(NaverCollector())
    if platforms in ("x", "all"):
        collectors.append(XTwitterCollector())
    if platforms in ("youtube", "all"):
        collectors.append(YouTubeCollector())
    if platforms in ("community", "all"):
        collectors.append(KoreanCommunityCollector())

    posts: list[dict] = []
    for kw in keywords[:10]:  # 최대 10개 키워드로 제한
        for collector in collectors:
            try:
                results = await collector.search(kw, limit=25)
                posts.extend(results)
            except Exception as e:
                logger.warning("수집 실패 (%s / %s): %s", collector.__class__.__name__, kw, e)

    scanned = len(posts)
    threats_created = 0
    mock_count = 0

    pid = profile.profile_id if profile else None

    for post in posts:
        try:
            threat = await run_pipeline(post, user_id, db, pid)
            if threat:
                threats_created += 1
                if post.get("is_mock"):
                    mock_count += 1
        except Exception as e:
            logger.warning("파이프라인 실패 (계속 진행): %s", e)

    if threats_created:
        await db.commit()

    return {
        "scanned": scanned,
        "new_threats": threats_created,
        "mock_count": mock_count,
        "is_mock": mock_count > 0 and threats_created == mock_count,
    }
