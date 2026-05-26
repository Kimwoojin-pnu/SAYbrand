import asyncio

from backend.workers.celery_app import celery_app


@celery_app.task(name="backend.workers.alert_tasks.send_immediate_alert")
def send_immediate_alert(threat_id: int):
    """Critical 위협 즉각 알림 — 수집 직후 발행"""
    asyncio.run(_send_immediate_async(threat_id))


async def _send_immediate_async(threat_id: int):
    from sqlalchemy import select
    from backend.db.database import AsyncSessionLocal
    from backend.services.notifier import send_alert
    from backend.models.orm import Threat

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Threat).where(Threat.id == threat_id))
        threat = result.scalar_one_or_none()
        if threat:
            await send_alert(threat, db)


@celery_app.task(name="backend.workers.alert_tasks.send_daily_reports")
def send_daily_reports():
    """일간 리포트 전체 발송 — 매일 오전 8시"""
    asyncio.run(_send_daily_async())


async def _send_daily_async():
    from sqlalchemy import select
    from backend.db.database import AsyncSessionLocal
    from backend.services.report_generator import generate_daily_report
    from backend.services.notifier import send_report_email
    from backend.models.orm import User

    async with AsyncSessionLocal() as db:
        users = await db.execute(
            select(User).where(User.subscription_status.in_(["active", "free"]))
        )
        for user in users.scalars():
            report = await generate_daily_report(user.id, db)
            if report["total_threats"] > 0:
                await send_report_email(user, report)


@celery_app.task(name="backend.workers.alert_tasks.send_weekly_reports")
def send_weekly_reports():
    """주간 리포트 — 매주 월요일"""
    asyncio.run(_send_weekly_async())


async def _send_weekly_async():
    # daily와 동일 구조, 기간만 7일로 변경 — 추후 구현
    pass


@celery_app.task(name="backend.workers.alert_tasks.process_grace_periods")
def process_grace_periods():
    """구독 유예기간 만료 처리 — 매일 새벽 1시"""
    asyncio.run(_process_grace_async())


async def _process_grace_async():
    from backend.db.database import AsyncSessionLocal
    from backend.services.org_service import process_expired_grace_periods

    async with AsyncSessionLocal() as db:
        await process_expired_grace_periods(db)
