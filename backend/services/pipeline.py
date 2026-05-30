"""
분석 파이프라인 — ProfileLoader → L1 → Entity Resolver → L2 → L3 → DB 저장
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.orm import Keyword, Threat
from backend.services.analyzers.l1_filter import l1_filter, l1_filter_with_profile
from backend.services.analyzers.l2_text import analyze_text_with_cache, analyze_batch
from backend.services.profile_loader import profile_loader
from backend.services.reach_calculator import estimate_reach
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

L3_SCORE_THRESHOLD = 0.85


_L2_MOCK = {
    "threat_detected": False, "severity": "none", "confidence": 0.0,
    "summary": "", "is_organized": False, "sentiment": "neutral",
    "emotion": "중립", "sentiment_score": 0.0, "is_mock": True,
}


async def run_pipeline(
    post: dict,
    user_id: int,
    db: AsyncSession,
    profile_id: int | None = None,
    org_id: int | None = None,
    include_l2: bool = True,
    precomputed_l2: dict | None = None,
) -> Threat | None:
    """
    단일 포스트를 L1→L2→L3 파이프라인으로 분석하고 DB에 저장한다.

    프로파일이 있으면 ProfileLoader 강화 필터 사용,
    없으면 기존 키워드 기반 l1_filter로 폴백.

    Returns:
        저장된 Threat 객체. L1 탈락 시 None.
    """
    # DB DateTime 컬럼은 naive UTC — timezone.utc 사용 시 asyncpg DataError
    now = datetime.utcnow()

    content_preview = post["content"][:80].replace("\n", " ")
    print(f"[PIPELINE 시작] {post.get('platform','?')}/{post.get('source_account','?')}: {content_preview}")

    # ── 프로파일 로드 ─────────────────────────────────────────────────
    profile = None
    if profile_id:
        profile = await profile_loader.load(profile_id, db)
    if not profile:
        profile = await profile_loader.load_for_user(user_id, db)

    # ── L1 필터 ───────────────────────────────────────────────────────

    if profile:
        aliases_preview = [a for a, _ in profile.aliases[:5]]
        print(f"[PROFILE] display_name={profile.display_name!r} aliases={aliases_preview} search_kw={profile.search_keywords[:3]}")
        l1 = await l1_filter_with_profile(
            content=post["content"],
            account_name=post.get("source_account", ""),
            profile=profile,
            search_keyword=post.get("_search_keyword", ""),
        )
    else:
        # 프로파일 없으면 키워드 기반 폴백
        kw_result = await db.execute(
            select(Keyword.keyword).where(Keyword.user_id == user_id, Keyword.active.is_(True))
        )
        brand_keywords = [r[0] for r in kw_result.all()]
        print(f"[PROFILE] 없음 — 키워드 폴백: {brand_keywords}")
        l1 = l1_filter(post["content"], brand_keywords=brand_keywords or None)

    print(f"[L1] pass={l1['pass']} score={l1['score']:.4f} severity={l1.get('severity')} brand={l1.get('brand_mentioned')} cats={l1.get('matched_categories')}")
    logger.info("[L1] pass=%s score=%.4f severity=%s brand_mentioned=%s cats=%s",
                l1["pass"], l1["score"], l1.get("severity"), l1.get("brand_mentioned"), l1.get("matched_categories"))

    if not l1["pass"]:
        print(f"[L1 탈락] score={l1['score']:.4f} brand={l1.get('brand_mentioned')} neg_filter={l1.get('negative_filter_applied')} reason={l1.get('reason','')}")
        logger.info("[L1] 탈락: score=%.4f brand=%s neg_filter=%s", l1["score"], l1.get("brand_mentioned"), l1.get("negative_filter_applied"))
        return None

    # ── 위협 유형 / 모듈 결정 ─────────────────────────────────────────
    module = l1.get("category") or "B"
    cats = l1.get("matched_categories", [])
    threat_type = _CATEGORY_TO_THREAT_TYPE.get(cats[0], "keyword_match") if cats else "keyword_match"

    # ── L2 텍스트 분석 ────────────────────────────────────────────────
    if precomputed_l2 is not None:
        l2 = precomputed_l2
    elif not include_l2:
        l2 = _L2_MOCK
    else:
        try:
            l2 = await asyncio.wait_for(
                analyze_text_with_cache(post["content"], profile_id),
                timeout=5.0,
            )
        except Exception:
            l2 = _L2_MOCK

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
        or l1.get("auto_critical", False)
        or (bool(exec_mentioned) and severity == "critical")
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
    # "feedback" 등급은 브랜드 언급은 됐으나 위협 패턴 미매칭 — 재분류 대상 아님
    if severity == "feedback":
        final_severity = "feedback"
    else:
        final_severity = classify_alert_threshold(risk_score_raw, profile)

    # ── 날짜 처리 ────────────────────────────────────────────────────
    published = post.get("published_at") or now
    # DB는 naive UTC — tz-aware datetime이면 UTC 변환 후 tzinfo 제거
    if hasattr(published, "tzinfo") and published.tzinfo is not None:
        published = published.astimezone(timezone.utc).replace(tzinfo=None)

    is_mock = post.get("is_mock", False)
    if l2.get("is_mock"):
        is_mock = True

    # ── DB 저장 ──────────────────────────────────────────────────────
    reach_estimate = estimate_reach(post["platform"])

    threat = Threat(
        user_id=user_id,
        org_id=org_id,
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
        sentiment=l2.get("sentiment"),
        emotion=l2.get("emotion"),
        sentiment_score=l2.get("sentiment_score"),
        reach_estimate=reach_estimate,
        status="active",
        post_published_at=published,
        engagements_per_hour=0.0,
        detected_at=now,
        updated_at=now,
    )
    db.add(threat)
    await db.flush()
    print(f"[PIPELINE 완료] threat.id={threat.id} severity={final_severity} risk={risk_score_raw} mock={is_mock}")

    if final_severity in ("critical", "high"):
        await _send_notifications(threat, user_id, db)

    return threat


async def _send_notifications(threat: Threat, user_id: int, db: AsyncSession) -> None:
    """critical·high 위협 발생 시 웹훅·Slack 알림 (실패해도 파이프라인 중단 없음)."""
    import json as _json
    from backend.models.orm import OutboundWebhook, OrganizationMember, Organization
    from backend.services.webhook_sender import send_webhook
    from backend.services.slack_notifier import send_slack_threat_alert

    payload = {
        "event": f"threat.{threat.severity}",
        "threat_id": threat.id,
        "severity": threat.severity,
        "threat_type": threat.threat_type,
        "platform": threat.platform,
        "source_account": threat.source_account,
        "content_preview": (threat.content_preview or "")[:200],
        "risk_score": threat.risk_score,
        "ai_analysis": threat.ai_analysis,
    }

    try:
        wh_result = await db.execute(
            select(OutboundWebhook).where(
                OutboundWebhook.user_id == user_id,
                OutboundWebhook.active.is_(True),
            )
        )
        for wh in wh_result.scalars().all():
            events = _json.loads(wh.events or "[]")
            if f"threat.{threat.severity}" in events:
                await send_webhook(wh.url, payload, wh.secret)
    except Exception as e:
        logger.warning("웹훅 알림 실패: %s", e)

    try:
        mem_result = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.user_id == user_id,
                OrganizationMember.status == "active",
            ).limit(1)
        )
        member = mem_result.scalar_one_or_none()
        if member:
            org_result = await db.execute(
                select(Organization).where(Organization.id == member.org_id)
            )
            org = org_result.scalar_one_or_none()
            if org and org.slack_webhook_url:
                await send_slack_threat_alert(org.slack_webhook_url, {
                    "severity": threat.severity,
                    "platform": threat.platform,
                    "source_account": threat.source_account,
                    "content_preview": threat.content_preview,
                    "threat_type": threat.threat_type,
                    "ai_analysis": threat.ai_analysis,
                })
    except Exception as e:
        logger.warning("Slack 알림 실패: %s", e)


async def run_scan(
    user_id: int,
    keywords: list[str],
    platforms: str,
    db: AsyncSession,
    profile_id: int | None = None,
    org_id: int | None = None,
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

    # 브랜드명 + 부정어 조합 검색 추가 — 부정 콘텐츠 수집 감도 향상
    _NEGATIVE_COMBOS = ["불만", "불매", "최악", "실망", "별로", "환불거부", "항의"]
    brand_names = (profile.search_keywords[:2] if profile else keywords[:2])
    negative_combos = [
        f"{b} {n}"
        for b in brand_names[:2]
        for n in _NEGATIVE_COMBOS[:4]
        if f"{b} {n}" not in keywords
    ]
    keywords = list(dict.fromkeys(keywords + negative_combos))

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
    for kw in keywords[:14]:  # 부정어 조합 포함 최대 14개
        for collector in collectors:
            try:
                results = await collector.search(kw, limit=25, days_back=7)
                for post in results:
                    post["_search_keyword"] = kw  # L1 brand 감지 힌트
                posts.extend(results)
            except Exception as e:
                logger.warning("수집 실패 (%s / %s): %s", collector.__class__.__name__, kw, e)

    scanned_raw = len(posts)
    # API 키 없을 때 수집기가 반환하는 mock 포스트는 DB에 저장하지 않는다
    real_posts = [p for p in posts if not p.get("is_mock")]
    mock_count = scanned_raw - len(real_posts)

    # URL 기준 중복 제거 후 최대 100건으로 제한 (Vercel 타임아웃 방지)
    seen_urls: set[str] = set()
    deduped: list[dict] = []
    for p in real_posts:
        key = p.get("post_url") or p["content"][:80]
        if key not in seen_urls:
            seen_urls.add(key)
            deduped.append(p)
    posts = deduped[:100]

    scanned = len(posts)
    print(f"[SCAN 수집] raw={scanned_raw} mock={mock_count} real={len(real_posts)} dedup={scanned}")

    threats_created = 0
    l1_pass = 0
    l1_fail = 0
    errors = 0

    pid = profile.profile_id if profile else None

    # ── L1 사전 필터 → L2 배치 분석 ──────────────────────────────────
    from backend.config import settings

    # 프로파일 없을 때 키워드 한 번만 로드
    brand_kws_fallback: list[str] = []
    if not profile:
        kw_rows = await db.execute(
            select(Keyword.keyword).where(Keyword.user_id == user_id, Keyword.active.is_(True))
        )
        brand_kws_fallback = [r[0] for r in kw_rows.all()]

    l1_passing_contents: list[str] = []
    for post in posts:
        try:
            if profile:
                l1_pre = await l1_filter_with_profile(
                    content=post["content"],
                    account_name=post.get("source_account", ""),
                    profile=profile,
                    search_keyword=post.get("_search_keyword", ""),
                )
            else:
                l1_pre = l1_filter(post["content"], brand_keywords=brand_kws_fallback or None)
            if l1_pre["pass"]:
                l1_passing_contents.append(post["content"])
        except Exception:
            pass

    # L1 통과 콘텐츠 → Gemini 배치 분석 (최대 10건씩)
    l2_by_content: dict[str, dict] = {}
    if l1_passing_contents and settings.gemini_api_key:
        try:
            for i in range(0, len(l1_passing_contents), 10):
                batch = l1_passing_contents[i:i + 10]
                results = await analyze_batch(batch, max_batch=10)
                for text, res in zip(batch, results):
                    l2_by_content[text[:200]] = res
            print(f"[L2 배치] {len(l1_passing_contents)}건 L1통과 → {len(l2_by_content)}건 분석 완료")
        except Exception as e:
            print(f"[L2 배치 오류] {type(e).__name__}: {e}")

    for post in posts:
        try:
            precomputed = l2_by_content.get(post["content"][:200])
            threat = await run_pipeline(post, user_id, db, pid, org_id=org_id,
                                        include_l2=False, precomputed_l2=precomputed)
            if threat:
                threats_created += 1
                l1_pass += 1
            else:
                l1_fail += 1
        except Exception as e:
            errors += 1
            print(f"[PIPELINE 오류] {type(e).__name__}: {e}")
            logger.warning("파이프라인 실패 (계속 진행): %s", e)

    if threats_created:
        await db.commit()

    print(f"[SCAN 완료] scanned={scanned} real={len(posts)+errors} mock={mock_count} l1_pass={l1_pass} l1_fail={l1_fail} errors={errors} new_threats={threats_created}")

    return {
        "scanned": scanned,
        "real": len(real_posts),
        "mock_count": mock_count,
        "l1_pass": l1_pass,
        "l1_fail": l1_fail,
        "errors": errors,
        "new_threats": threats_created,
        "is_mock": mock_count > 0 and len(real_posts) == 0,
    }
