worker: celery -A backend.workers.celery_app worker --loglevel=info --concurrency=4 -B
beat: celery -A backend.workers.celery_app beat --loglevel=info
flower: celery -A backend.workers.celery_app flower --port=5555
