import os
from celery import Celery

BROKER  = os.environ.get("CELERY_BROKER_URL",    "redis://redis:6379/0")
BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

celery_app = Celery("bytebeat", broker=BROKER, backend=BACKEND)

celery_app.conf.task_routes = {
    "ml_tasks.validate_instrument":    {"queue": "ml_queue"},
    "transcription_tasks.transcribe":  {"queue": "transcription_queue"},
    "generation_tasks.generate":       {"queue": "generation_queue"},
}
