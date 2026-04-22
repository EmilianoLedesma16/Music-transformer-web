import os
from celery import Celery

BROKER  = os.environ.get("CELERY_BROKER_URL",    "redis://redis:6379/0")
BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

celery_app = Celery("ml_tasks", broker=BROKER, backend=BACKEND)


@celery_app.task(name="ml_tasks.validate_instrument")
def validate_instrument(creacion_id: int, audio_path: str, genre: str, mood: str,
                        energy: str, instrument: str, temperature: float, top_p: float):
    from db import update_creacion
    from classifier import classify_instrument

    update_creacion(creacion_id, status="VALIDATING")

    detected, is_valid = classify_instrument(audio_path)
    update_creacion(creacion_id, detected_instrument=detected)

    if not is_valid:
        update_creacion(
            creacion_id,
            status        = "FAILED",
            error_message = (
                f"Instrumento detectado '{detected}' no está soportado. "
                "Solo se acepta piano, guitar o bass."
            ),
        )
        return

    celery_app.send_task(
        "transcription_tasks.transcribe",
        args=[creacion_id, audio_path, genre, mood, energy, instrument, temperature, top_p],
        queue="transcription_queue",
    )
