import os
from celery import Celery

BROKER  = os.environ.get("CELERY_BROKER_URL",    "redis://redis:6379/0")
BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

celery_app = Celery("audio_tasks", broker=BROKER, backend=BACKEND)


@celery_app.task(name="audio_tasks.run_pipeline")
def run_pipeline(gen_id, audio_path, genre, mood, instrument,
                 temperature, top_p):
    from orchestrator import run
    run(gen_id, audio_path, genre, mood, instrument, temperature, top_p)
