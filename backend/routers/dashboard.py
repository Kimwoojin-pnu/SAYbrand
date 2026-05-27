from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.db.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.org_context import optional_current_org, require_non_viewer
from backend.models.orm import CompetitorMention, HashtagTrend, Keyword, Threat, Alert, User, Organization
from backend.models.schemas import (
    AlertResponse,
    ModuleScore,
    RiskScoreResponse,
    StatsResponse,
    StatusUpdateRequest,
    ThreatBase,
    ThreatListResponse,
)
from backend.db.seed import _THREATS as _SEED_THREATS

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# ── 비로그인 UI 미리보기용 정적 Mock 응답 ──────────────────────────────────────

def _mock_stats() -> StatsResponse:
    return StatsResponse(total=16, critical=2, high=3, medium=5, low=6, active=10, reviewing=2, resolved=4)


def _mock_risk() -> RiskScoreResponse:
    return RiskScoreResponse(
        overall=61.5,
        module_a=ModuleScore(module="A", score=72.0, threat_count=5),
        module_b=ModuleScore(module="B", score=58.0, threat_count=7),
        module_c=ModuleScore(module="C", score=49.0, threat_count=4),
        level="HIGH",
    )


def _mock_threats_list(page: int, page_size: int) -> ThreatListResponse:
    now = datetime.now(timezone.utc)
    all_items = []
    for i, t in enumerate(_SEED_THREATS):
        detected = now - timedelta(minutes=t["minutes_ago"])
        all_items.append(ThreatBase(
            id=9000 + i,
            module=t["module"], threat_type=t["threat_type"],
            severity=t["severity"], platform=t["platform"],
            source_account=t["source_account"], source_url=t["source_url"],
            content_preview=t["content_preview"],
            confidence=t["confidence"], risk_score=t["risk_score"],
            ai_analysis=t.get("ai_analysis"),
            ai_response_suggestion=t.get("ai_response_suggestion"),
            bot_probability=t.get("bot_probability"),
            is_organized=t.get("is_organized"),
            status=t["status"],
            detected_at=detected, updated_at=detected,
            engagements_per_hour=0.0,
        ))
    start = (page - 1) * page_size
    return ThreatListResponse(items=all_items[start:start + page_size], total=len(all_items), page=page, page_size=page_size)


def _mock_alerts() -> list[dict]:
    now = datetime.now(timezone.utc)
    msgs = [
        ("critical", "사칭 계정 탐지: @saybrand_official_kr (인스타그램)", 8),
        ("critical", "CEO 사칭 계정 확산 경보 — 봇 확률 83%", 22),
        ("high", "허위 원료 정보 유튜브 영상 조회수 48만 돌파", 45),
        ("high", "고객 데이터 유출 허위 주장 스토리 8,200회 공유", 90),
        ("high", "CFO 관련 루머 X(트위터) 빠른 확산 감지", 130),
    ]
    return [
        {"id": i + 1, "threat_id": 9001 + i, "severity": sev, "message": msg,
         "channel": "dashboard", "sent_at": now - timedelta(minutes=mins)}
        for i, (sev, msg, mins) in enumerate(msgs)
    ]


def _mock_trend() -> dict:
    labels = [f"{i}일전" for i in range(6, 0, -1)] + ["오늘"]
    return {"labels": labels, "module_a": [1, 2, 1, 3, 2, 1, 2], "module_b": [2, 1, 3, 2, 3, 4, 2], "module_c": [1, 0, 1, 2, 1, 1, 1]}


def _mock_platform_stats() -> list[dict]:
    return [
        {"platform": "instagram", "count": 5, "pct": 31},
        {"platform": "x", "count": 4, "pct": 25},
        {"platform": "youtube", "count": 3, "pct": 19},
        {"platform": "tiktok", "count": 1, "pct": 6},
        {"platform": "naver", "count": 3, "pct": 19},
    ]


def _apply_org_filter(query, org: Organization | None, user_id: int | None = None):
    if org is not None:
        return query.where(Threat.org_id == org.id)
    if user_id:
        return query.where(Threat.user_id == user_id)
    return query


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    request: Request,
    org: Organization | None = Depends(optional_current_org),
    db: AsyncSession = Depends(get_db),
):
    user_id = request.session.get("user_id")
    if not user_id:
        return _mock_stats()

    sev_result = await db.execute(
        _apply_org_filter(
            select(Threat.severity, func.count(Threat.id)).group_by(Threat.severity),
            org, user_id,
        )
    )
    sev = {row[0]: row[1] for row in sev_result}

    status_result = await db.execute(
        _apply_org_filter(
            select(Threat.status, func.count(Threat.id)).group_by(Threat.status),
            org, user_id,
        )
    )
    sta = {row[0]: row[1] for row in status_result}

    total = await db.execute(
        _apply_org_filter(select(func.count(Threat.id)), org, user_id)
    )

    return StatsResponse(
        total=total.scalar(),
        critical=sev.get("critical", 0),
        high=sev.get("high", 0),
        medium=sev.get("medium", 0),
        low=sev.get("low", 0),
        active=sta.get("active", 0),
        reviewing=sta.get("reviewing", 0),
        resolved=sta.get("resolved", 0),
    )


@router.get("/risk-score", response_model=RiskScoreResponse)
async def get_risk_score(
    request: Request,
    org: Organization | None = Depends(optional_current_org),
    db: AsyncSession = Depends(get_db),
):
    user_id = request.session.get("user_id")
    if not user_id:
        return _mock_risk()

    result = await db.execute(
        _apply_org_filter(
            select(Threat.module, func.avg(Threat.risk_score), func.count(Threat.id))
            .group_by(Threat.module),
            org, user_id,
        )
    )
    module_data = {row[0]: {"avg": float(row[1] or 0), "count": row[2]} for row in result}

    a = module_data.get("A", {"avg": 0, "count": 0})
    b = module_data.get("B", {"avg": 0, "count": 0})
    c = module_data.get("C", {"avg": 0, "count": 0})

    overall = a["avg"] * 0.40 + b["avg"] * 0.35 + c["avg"] * 0.25

    if overall >= 80:
        level = "CRITICAL"
    elif overall >= 60:
        level = "HIGH"
    elif overall >= 35:
        level = "MEDIUM"
    else:
        level = "LOW"

    return RiskScoreResponse(
        overall=round(overall, 1),
        module_a=ModuleScore(module="A", score=round(a["avg"], 1), threat_count=a["count"]),
        module_b=ModuleScore(module="B", score=round(b["avg"], 1), threat_count=b["count"]),
        module_c=ModuleScore(module="C", score=round(c["avg"], 1), threat_count=c["count"]),
        level=level,
    )


@router.get("/threats", response_model=ThreatListResponse)
async def get_threats(
    request: Request,
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    org: Organization | None = Depends(optional_current_org),
    db: AsyncSession = Depends(get_db),
):
    user_id = request.session.get("user_id")
    if not user_id:
        return _mock_threats_list(page, page_size)

    base = _apply_org_filter(select(Threat), org, user_id)
    count_base = _apply_org_filter(select(func.count(Threat.id)), org, user_id)

    if severity:
        base = base.where(Threat.severity == severity)
        count_base = count_base.where(Threat.severity == severity)
    if status:
        base = base.where(Threat.status == status)
        count_base = count_base.where(Threat.status == status)

    total = (await db.execute(count_base)).scalar()
    items_result = await db.execute(
        base.order_by(Threat.risk_score.desc(), Threat.detected_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = items_result.scalars().all()

    return ThreatListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/alerts", response_model=list[AlertResponse])
async def get_alerts(
    request: Request,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    if not request.session.get("user_id"):
        return _mock_alerts()
    result = await db.execute(select(Alert).order_by(Alert.sent_at.desc()).limit(limit))
    return result.scalars().all()


@router.patch("/threats/{threat_id}/status")
async def update_threat_status(
    threat_id: int,
    body: StatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Threat).where(Threat.id == threat_id))
    threat = result.scalar_one_or_none()
    if not threat:
        raise HTTPException(status_code=404, detail="Threat not found")
    if body.status not in ("active", "reviewing", "resolved"):
        raise HTTPException(status_code=400, detail="Invalid status value")

    threat.status = body.status
    threat.updated_at = datetime.utcnow()
    await db.commit()
    return {"id": threat_id, "status": body.status}


class ResolveRequest(BaseModel):
    resolution_type: str   # "false_positive" | "real_resolved"
    resolution_method: str = ""
    resolution_note: str = ""


@router.patch("/threats/{threat_id}/resolve")
async def resolve_threat(
    threat_id: int,
    body: ResolveRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if body.resolution_type not in ("false_positive", "real_resolved"):
        raise HTTPException(status_code=400, detail="resolution_type must be false_positive or real_resolved")

    result = await db.execute(select(Threat).where(Threat.id == threat_id))
    threat = result.scalar_one_or_none()
    if not threat:
        raise HTTPException(status_code=404, detail="Threat not found")

    threat.status = "resolved"
    threat.resolution_type = body.resolution_type
    threat.resolution_method = body.resolution_method
    threat.resolution_note = body.resolution_note
    threat.updated_at = datetime.utcnow()
    await db.commit()
    return {"id": threat_id, "status": "resolved", "resolution_type": body.resolution_type}


_CATEGORY_TO_THREAT_TYPE: dict[str, str] = {
    "A1_impersonation_account":  "account_impersonation",
    "A2_ceo_impersonation":      "account_impersonation",
    "A3_product_counterfeit":    "logo_spoof",
    "A4_logo_visual_abuse":      "logo_spoof",
    "B1_product_safety_crisis":  "organized_rumor",
    "B2_legal_crisis":           "organized_rumor",
    "B3_financial_crisis":       "organized_rumor",
    "B4_organized_attack_bot":   "organized_rumor",
    "B5_consumer_complaint_high":"reputation_attack",
    "B6_consumer_complaint_mid": "negative_comment",
    "B7_fake_news_patterns":     "viral_rumor",
    "B8_crisis_escalation":      "viral_rumor",
    "B9_competitor_attack":      "competitor_mention",
    "C1_executive_misconduct":   "reputation_attack",
    "C2_internal_leak":          "organized_rumor",
    "C3_labor_issue":            "negative_comment",
    "C4_privacy_surveillance":   "organized_rumor",
    "KR_community_slang":        "negative_comment",
    "KR_sns_attack_patterns":    "organized_rumor",
    "CRITICAL_BYPASS":           "organized_rumor",
}


@router.get("/trend")
async def get_trend(
    request: Request,
    org: Organization | None = Depends(optional_current_org),
    db: AsyncSession = Depends(get_db),
):
    """최근 7일 모듈별 위협 건수 반환."""
    user_id = request.session.get("user_id")
    if not user_id:
        return _mock_trend()

    now = datetime.now(timezone.utc)
    labels = []
    module_a, module_b, module_c = [], [], []

    for i in range(6, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)
        labels.append("오늘" if i == 0 else f"{i}일전")

        for module, lst in (("A", module_a), ("B", module_b), ("C", module_c)):
            base_q = select(func.count(Threat.id)).where(
                Threat.module == module,
                Threat.detected_at >= day_start,
                Threat.detected_at < day_end,
            )
            if org is not None:
                base_q = base_q.where(Threat.org_id == org.id)
            elif user_id:
                base_q = base_q.where(Threat.user_id == user_id)
            cnt = (await db.execute(base_q)).scalar() or 0
            lst.append(cnt)

    return {"labels": labels, "module_a": module_a, "module_b": module_b, "module_c": module_c}


@router.get("/platform-stats")
async def get_platform_stats(
    request: Request,
    org: Organization | None = Depends(optional_current_org),
    db: AsyncSession = Depends(get_db),
):
    """플랫폼별 위협 건수 반환."""
    user_id = request.session.get("user_id")
    if not user_id:
        return _mock_platform_stats()

    base_q = select(Threat.platform, func.count(Threat.id)).group_by(Threat.platform)
    if org is not None:
        base_q = base_q.where(Threat.org_id == org.id)
    elif user_id:
        base_q = base_q.where(Threat.user_id == user_id)
    result = await db.execute(base_q)
    data = {row[0]: row[1] for row in result}
    total = sum(data.values()) or 1
    platforms = ["instagram", "x", "youtube", "tiktok", "naver"]
    return [
        {"platform": p, "count": data.get(p, 0), "pct": round(data.get(p, 0) / total * 100)}
        for p in platforms
    ]


class ScanRequest(BaseModel):
    keywords: list[str] = []
    platforms: str = "all"


@router.post("/scan")
async def post_scan(
    body: ScanRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
    _: None = Depends(require_non_viewer),
):
    """
    Vercel: Celery 워커(Railway)에 태스크 발행.
    로컬: Celery 없으면 직접 실행 fallback.
    """
    from backend.config import settings
    from backend.models.orm import CustomerProfile

    uid = user["id"]

    if settings.is_vercel:
        # Vercel 환경: Railway 워커에 태스크 발행
        profile_result = await db.execute(
            select(CustomerProfile).where(CustomerProfile.user_id == uid)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            return {"success": False, "message": "프로파일을 먼저 등록해주세요."}

        try:
            from backend.workers.collection_tasks import collect_single_profile
            task = collect_single_profile.delay(profile.id, uid)
            return {
                "success": True,
                "task_id": task.id,
                "message": "수집을 시작했습니다. 30초 후 새로고침하세요.",
                "is_async": True,
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"워커 서버에 연결할 수 없습니다: {str(e)}",
            }

    # 로컬 환경: 직접 실행
    from backend.services.pipeline import run_scan

    keywords = body.keywords
    if not keywords:
        kw_result = await db.execute(
            select(Keyword.keyword).where(Keyword.user_id == uid, Keyword.active.is_(True))
        )
        keywords = [r[0] for r in kw_result.all()]

    if not keywords:
        raise HTTPException(status_code=400, detail="등록된 키워드가 없습니다. 먼저 키워드를 추가해 주세요.")

    result = await run_scan(uid, keywords, body.platforms, db, org_id=org.id if org else None)
    return result


@router.post("/scan-local")
async def post_scan_local(
    body: ScanRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
    _: None = Depends(require_non_viewer),
):
    """
    로컬 개발 전용: Celery 없이 직접 실행.
    프로덕션(Vercel)에서는 비활성화.
    """
    from backend.config import settings
    if settings.is_vercel:
        raise HTTPException(status_code=403, detail="프로덕션에서는 사용 불가")

    from backend.services.pipeline import run_scan

    uid = user["id"]
    keywords = body.keywords
    if not keywords:
        kw_result = await db.execute(
            select(Keyword.keyword).where(Keyword.user_id == uid, Keyword.active.is_(True))
        )
        keywords = [r[0] for r in kw_result.all()]

    if not keywords:
        raise HTTPException(status_code=400, detail="등록된 키워드가 없습니다. 먼저 키워드를 추가해 주세요.")

    result = await run_scan(uid, keywords, body.platforms, db, org_id=org.id if org else None)
    return result


@router.get("/sentiment-trend")
async def get_sentiment_trend(
    request: Request,
    org: Organization | None = Depends(optional_current_org),
    db: AsyncSession = Depends(get_db),
):
    """최근 7일 일별 감성 분포 (negative/positive/neutral 건수)."""
    user_id = request.session.get("user_id")
    if not user_id:
        labels = [f"{i}일전" for i in range(6, 0, -1)] + ["오늘"]
        return {"labels": labels, "negative": [3,2,4,3,5,4,3], "positive": [2,3,2,4,3,2,3], "neutral": [1,1,1,2,1,1,2]}

    now = datetime.now(timezone.utc)
    labels, negative, positive, neutral = [], [], [], []

    for i in range(6, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        labels.append("오늘" if i == 0 else f"{i}일전")

        for sentiment, lst in (("negative", negative), ("positive", positive), ("neutral", neutral)):
            q = select(func.count(Threat.id)).where(
                Threat.sentiment == sentiment,
                Threat.detected_at >= day_start,
                Threat.detected_at < day_end,
            )
            if org is not None:
                q = q.where(Threat.org_id == org.id)
            elif user_id:
                q = q.where(Threat.user_id == user_id)
            cnt = (await db.execute(q)).scalar() or 0
            lst.append(cnt)

    return {"labels": labels, "negative": negative, "positive": positive, "neutral": neutral}


@router.get("/share-of-voice")
async def get_share_of_voice(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """경쟁사 대비 언급량 점유율."""
    brand_result = await db.execute(
        select(func.count(Threat.id)).where(Threat.user_id == user["id"])
    )
    brand_count = brand_result.scalar() or 0

    comp_result = await db.execute(
        select(CompetitorMention.competitor_name, func.count(CompetitorMention.id))
        .where(CompetitorMention.user_id == user["id"])
        .group_by(CompetitorMention.competitor_name)
    )
    competitors = {row[0]: row[1] for row in comp_result}

    total = brand_count + sum(competitors.values()) or 1
    items = [{"name": "내 브랜드", "count": brand_count, "pct": round(brand_count / total * 100, 1)}]
    for name, cnt in competitors.items():
        items.append({"name": name, "count": cnt, "pct": round(cnt / total * 100, 1)})

    return {"items": items, "total": total}


@router.get("/hashtags")
async def get_hashtag_trends(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """최근 해시태그 트렌드."""
    result = await db.execute(
        select(HashtagTrend)
        .where(HashtagTrend.user_id == user["id"])
        .order_by(HashtagTrend.mention_count.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "hashtag": r.hashtag,
            "platform": r.platform,
            "mention_count": r.mention_count,
            "sentiment": r.sentiment,
            "trend_date": r.trend_date.isoformat() if r.trend_date else None,
        }
        for r in rows
    ]


@router.get("/top-influencers")
async def get_top_influencers(
    request: Request,
    limit: int = Query(10, ge=1, le=50),
    org: Organization | None = Depends(optional_current_org),
    db: AsyncSession = Depends(get_db),
):
    """위협 발생 계정 중 반복 등장 Top N."""
    user_id = request.session.get("user_id")
    if not user_id:
        return [
            {"account": "@saybrand_official_kr", "platform": "instagram", "mention_count": 3},
            {"account": "@SAYbrand_Ofcl", "platform": "x", "mention_count": 2},
        ]

    base_q = (
        select(Threat.source_account, Threat.platform, func.count(Threat.id).label("mention_count"))
        .where(Threat.source_account != "")
        .group_by(Threat.source_account, Threat.platform)
        .order_by(func.count(Threat.id).desc())
        .limit(limit)
    )
    if org is not None:
        base_q = base_q.where(Threat.org_id == org.id)
    else:
        base_q = base_q.where(Threat.user_id == user_id)
    result = await db.execute(base_q)
    return [
        {"account": row[0], "platform": row[1], "mention_count": row[2]}
        for row in result
    ]


@router.get("/anomaly")
async def get_anomaly(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """1시간 위협 급증 이상 감지."""
    from backend.services.anomaly_detector import detect_anomaly
    return await detect_anomaly(user["id"], db)


@router.get("/scan")
async def manual_scan(
    keyword: str = Query(..., description="검색 키워드"),
    platforms: str = Query("all", description="naver | x | all"),
    db: AsyncSession = Depends(get_db),
):
    """
    키워드로 Naver·X를 수집하고 L1 필터를 통과한 결과를 Threat으로 저장한다.
    API 키 없으면 Mock 데이터로 동작한다.
    """
    from backend.services.collectors.naver import NaverCollector
    from backend.services.collectors.x_twitter import XTwitterCollector
    from backend.services.analyzers.l1_filter import l1_filter

    # 데모/MVP — 첫 번째 유저에 귀속
    user_result = await db.execute(select(User).limit(1))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="등록된 유저가 없습니다")

    posts: list[dict] = []
    if platforms in ("naver", "all"):
        posts += await NaverCollector().search(keyword, limit=25)
    if platforms in ("x", "all"):
        posts += await XTwitterCollector().search(keyword, limit=10)

    now = datetime.now(timezone.utc)
    threats_created = 0

    for post in posts:
        result = l1_filter(post["content"], brand_keywords=[keyword])
        if not result["pass"]:
            continue

        cats = result.get("matched_categories", [])
        threat_type = _CATEGORY_TO_THREAT_TYPE.get(cats[0], "keyword_match") if cats else "keyword_match"
        module = cats[0][0] if cats and cats[0][0] in ("A", "B", "C") else "B"

        published = post.get("published_at") or now
        # published가 naive datetime이면 UTC로 간주
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)

        threat = Threat(
            user_id=user.id,
            module=module,
            threat_type=threat_type,
            severity=result["severity"] or "low",
            platform=post["platform"],
            source_account=post["source_account"],
            source_url=post["post_url"],
            content_preview=post["content"][:500],
            confidence=result["score"],
            risk_score=int(result["score"] * 100),
            bot_probability=None,
            is_organized=False,
            post_published_at=published,
            engagements_per_hour=0.0,
            detected_at=now,
            updated_at=now,
        )
        db.add(threat)
        threats_created += 1

    if threats_created:
        await db.commit()

    return {
        "keyword": keyword,
        "platforms": platforms,
        "collected": len(posts),
        "l1_passed": threats_created,
        "threats_created": threats_created,
    }
