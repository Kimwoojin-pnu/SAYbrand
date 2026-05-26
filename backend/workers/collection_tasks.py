import asyncio
import logging

from backend.workers.celery_app import celery_app
from backend.db.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(name="backend.workers.collection_tasks.collect_all_profiles")
def collect_all_profiles():
    """모든 활성 고객 프로파일 수집 — 30분마다 실행"""
    asyncio.run(_collect_all_profiles_async())


async def _collect_all_profiles_async():
    from sqlalchemy import select
    from backend.models.orm import CustomerProfile, User

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CustomerProfile)
            .join(User)
            .where(User.subscription_status.in_(["active", "free"]))
        )
        profiles = result.scalars().all()

        logger.info(f"수집 시작: {len(profiles)}개 프로파일")

        for profile_orm in profiles:
            try:
                from backend.services.collectors.orchestrator import collect_for_profile
                from backend.services.profile_loader import ProfileLoader
                from backend.services.pipeline import run_pipeline

                profile = await ProfileLoader().load(profile_orm.id, db)
                raw_posts = await collect_for_profile(profile)

                new_threats = 0
                for post in raw_posts:
                    threat = await run_pipeline(
                        raw_post=post,
                        user_id=profile_orm.user_id,
                        db=db,
                    )
                    if threat:
                        new_threats += 1
                        if threat.severity == "critical":
                            from backend.workers.alert_tasks import send_immediate_alert
                            send_immediate_alert.delay(threat.id)

                logger.info(
                    f"[{profile.display_name}] "
                    f"수집 {len(raw_posts)}건 → 위협 {new_threats}건"
                )
            except Exception as e:
                logger.error(f"프로파일 {profile_orm.id} 수집 실패: {e}")
                continue


@celery_app.task(name="backend.workers.collection_tasks.collect_single_profile")
def collect_single_profile(profile_id: int, user_id: int):
    """단일 프로파일 즉시 수집 — Vercel의 [스캔 실행] 버튼에서 발행"""
    asyncio.run(_collect_single_async(profile_id, user_id))


async def _collect_single_async(profile_id: int, user_id: int):
    from backend.services.collectors.orchestrator import collect_for_profile
    from backend.services.profile_loader import ProfileLoader
    from backend.services.pipeline import run_pipeline

    async with AsyncSessionLocal() as db:
        profile = await ProfileLoader().load(profile_id, db)
        raw_posts = await collect_for_profile(profile)
        new_threats = 0
        for post in raw_posts:
            threat = await run_pipeline(post, user_id, db)
            if threat:
                new_threats += 1
        return {"collected": len(raw_posts), "threats": new_threats}


@celery_app.task(name="backend.workers.collection_tasks.purge_expired_data")
def purge_expired_data():
    """90일 초과 데이터 삭제 — 매일 자정 실행"""
    asyncio.run(_purge_async())


async def _purge_async():
    from datetime import datetime, timedelta
    from sqlalchemy import delete
    from backend.models.orm import Threat

    async with AsyncSessionLocal() as db:
        cutoff = datetime.utcnow() - timedelta(days=90)
        result = await db.execute(
            delete(Threat).where(Threat.detected_at < cutoff)
        )
        await db.commit()
        logger.info(f"만료 데이터 삭제: {result.rowcount}건")


