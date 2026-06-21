import asyncio
import logging

from backend.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_UNANALYZED_BATCH_SIZE = 10  # 1회 최대 처리 건수


@celery_app.task(
    name="backend.workers.analysis_tasks.analyze_threat",
    max_retries=3,
    default_retry_delay=60,
)
def analyze_threat(threat_id: int):
    """
    단일 위협 L3 심층 분석 — 고위협 케이스에서 개별 발행.
    Vercel에서 직접 처리하지 않고 Railway 워커에 위임.
    """
    asyncio.run(_analyze_async(threat_id))


async def _analyze_async(threat_id: int):
    from sqlalchemy import select
    from backend.db.database import AsyncSessionLocal
    from backend.models.orm import Threat
    from backend.services.analyzers.l3_deep import analyze as l3_analyze

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Threat).where(Threat.id == threat_id))
        threat = result.scalar_one_or_none()
        if not threat:
            return

        analysis = await l3_analyze(
            content=threat.content_preview,
            threat_type=threat.threat_type,
            severity=threat.severity,
            db=db,
            source_account=threat.source_account,
        )
        _apply_analysis(threat, analysis)
        await db.commit()


@celery_app.task(name="backend.workers.analysis_tasks.analyze_unanalyzed_critical_threats")
def analyze_unanalyzed_critical_threats():
    """
    15분마다 실행 — critical 등급이면서 ai_analysis가 없는 위협을 찾아 L3 분석 시작.
    오탐(is_false_positive=true) 판정 시 severity를 low로 다운그레이드.
    """
    asyncio.run(_scan_and_analyze_critical())


async def _scan_and_analyze_critical():
    from sqlalchemy import select, or_
    from backend.db.database import AsyncSessionLocal
    from backend.models.orm import Threat, Organization
    from backend.services.analyzers.l3_deep import analyze as l3_analyze
    from backend.services.slack_notifier import send_slack_threat_alert

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Threat)
            .where(
                Threat.severity.in_(["critical", "high"]),
                or_(
                    Threat.ai_analysis.is_(None),
                    Threat.ai_analysis.like("[Mock]%"),
                ),
                Threat.status == "active",
            )
            .limit(_UNANALYZED_BATCH_SIZE)
        )
        threats = result.scalars().all()

        if not threats:
            logger.info("analyze_unanalyzed_critical_threats: 미분석 위협 없음")
            return

        logger.info("analyze_unanalyzed_critical_threats: %d건 L3 분석 시작", len(threats))

        for threat in threats:
            try:
                analysis = await l3_analyze(
                    content=threat.content_preview,
                    threat_type=threat.threat_type,
                    severity=threat.severity,
                    db=db,
                    source_account=threat.source_account,
                )
                ai_text = analysis.get("ai_analysis", "")
                if ai_text.startswith("[Mock]"):
                    logger.info("  threat_id=%d L3 여전히 Mock — 건너뜀", threat.id)
                    continue

                _apply_analysis(threat, analysis)
                logger.info(
                    "  threat_id=%d L3 완료 — is_false_positive=%s severity=%s",
                    threat.id,
                    analysis.get("is_false_positive"),
                    threat.severity,
                )

                if not analysis.get("is_false_positive") and threat.org_id:
                    org_result = await db.execute(
                        select(Organization).where(Organization.id == threat.org_id)
                    )
                    org = org_result.scalar_one_or_none()
                    if org and org.slack_webhook_url:
                        await send_slack_threat_alert(org.slack_webhook_url, {
                            "severity": threat.severity,
                            "platform": threat.platform,
                            "source_account": threat.source_account,
                            "content_preview": threat.content_preview,
                            "threat_type": threat.threat_type,
                            "ai_analysis": analysis.get("ai_analysis"),
                            "ai_response_suggestion": analysis.get("ai_response_suggestion"),
                        })
            except Exception as e:
                logger.warning("  threat_id=%d L3 분석 실패: %s", threat.id, e)

        await db.commit()


def _apply_analysis(threat, analysis: dict) -> None:
    """L3 분석 결과를 위협 레코드에 적용. 오탐이면 severity를 low로 다운그레이드."""
    from datetime import datetime

    threat.ai_analysis = analysis.get("ai_analysis")
    threat.ai_response_suggestion = analysis.get("ai_response_suggestion")
    threat.updated_at = datetime.utcnow()

    if analysis.get("is_false_positive"):
        threat.severity = "low"
        prefix = "[L3 오탐 판정] "
        if threat.ai_analysis and not threat.ai_analysis.startswith(prefix):
            threat.ai_analysis = prefix + threat.ai_analysis
