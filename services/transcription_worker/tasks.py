import os
from celery import Celery

BROKER  = os.environ.get("CELERY_BROKER_URL",    "redis://redis:6379/0")
BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

celery_app = Celery("transcription_tasks", broker=BROKER, backend=BACKEND)


@celery_app.task(name="transcription_tasks.transcribe")
def transcribe(creacion_id: int, audio_path: str, genre: str, mood: str,
               energy: str, instrument: str, temperature: float, top_p: float):
    from db import update_creacion
    from transcriber import audio_to_midi

    update_creacion(creacion_id, status="TRANSCRIBING")

    try:
        midi_path = audio_to_midi(audio_path, creacion_id)
        update_creacion(creacion_id, midi_path=midi_path)

        celery_app.send_task(
            "generation_tasks.generate",
            args=[creacion_id, midi_path, genre, mood, energy, instrument, temperature, top_p],
            queue="generation_queue",
        )
    except Exception as exc:
        update_creacion(
            creacion_id,
            status        = "FAILED",
            error_message = f"Error en transcripción: {exc}",
        )
        raise
