from celery import Celery
from celery.schedules import crontab
from backend.config import settings

celery_app = Celery(
    "saybrand",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "backend.workers.collection_tasks",
        "backend.workers.analysis_tasks",
        "backend.workers.alert_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=300,
    task_time_limit=600,
)

celery_app.conf.beat_schedule = {
    # 30분마다 모든 고객 키워드 수집
    "collect-all-profiles": {
        "task": "backend.workers.collection_tasks.collect_all_profiles",
        "schedule": crontab(minute="*/30"),
        "options": {"expires": 25 * 60},
    },
    # 매일 오전 8시 일간 리포트 발송
    "daily-report": {
        "task": "backend.workers.alert_tasks.send_daily_reports",
        "schedule": crontab(hour=8, minute=0),
    },
    # 매주 월요일 오전 9시 주간 리포트
    "weekly-report": {
        "task": "backend.workers.alert_tasks.send_weekly_reports",
        "schedule": crontab(hour=9, minute=0, day_of_week=1),
    },
    # 자정: 90일 초과 데이터 삭제 (개인정보보호법)
    "purge-expired-data": {
        "task": "backend.workers.collection_tasks.purge_expired_data",
        "schedule": crontab(hour=0, minute=0),
    },
    # 매일 새벽 1시: 구독 유예기간 만료 처리
    "process-grace-periods": {
        "task": "backend.workers.alert_tasks.process_grace_periods",
        "schedule": crontab(hour=1, minute=0),
    },
}
