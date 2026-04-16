import os
from celery import Celery

BROKER  = os.environ.get("CELERY_BROKER_URL",    "redis://redis:6379/0")
BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

celery_app = Celery("generation_tasks", broker=BROKER, backend=BACKEND)


@celery_app.task(name="generation_tasks.generate")
def generate(creacion_id: int, midi_path: str, genre: str, mood: str,
             instrument: str, temperature: float, top_p: float):
    from orchestrator import run
    run(creacion_id, midi_path, genre, mood, instrument, temperature, top_p)
