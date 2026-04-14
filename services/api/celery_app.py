import os
from celery import Celery

BROKER  = os.environ.get("CELERY_BROKER_URL",    "redis://redis:6379/0")
BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

celery_app = Celery("music_transformer", broker=BROKER, backend=BACKEND)

celery_app.conf.task_routes = {
    "ml_tasks.validate_instrument": {"queue": "ml_queue"},
    "audio_tasks.run_pipeline":     {"queue": "audio_queue"},
}
