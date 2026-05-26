import asyncio

from backend.workers.celery_app import celery_app


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
    from backend.services.analyzers.l3_deep import deep_analyze

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Threat).where(Threat.id == threat_id))
        threat = result.scalar_one_or_none()
        if not threat:
            return

        analysis = await deep_analyze(
            content=threat.content_preview,
            platform=threat.platform,
            account=threat.source_account,
            profile_context={},
        )
        threat.ai_analysis = analysis.get("analysis")
        threat.ai_response_suggestion = analysis.get("response_suggestion")
        await db.commit()
