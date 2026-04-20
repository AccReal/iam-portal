from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "iam_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    beat_schedule={
        "rotate-passwords-daily": {
            "task": "app.tasks.password_rotation.rotate_expired_passwords",
            "schedule": crontab(hour=3, minute=0),  # 3:00 AM MSK
        },
    },
)
