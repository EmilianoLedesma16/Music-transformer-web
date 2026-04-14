import os
from celery import Celery

BROKER  = os.environ.get("CELERY_BROKER_URL",    "redis://redis:6379/0")
BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

celery_app = Celery("ml_tasks", broker=BROKER, backend=BACKEND)


@celery_app.task(name="ml_tasks.validate_instrument")
def validate_instrument(gen_id, audio_path, genre, mood, instrument,
                        temperature, top_p):
    from db import update_generation
    from classifier import classify_instrument

    update_generation(gen_id, status="VALIDATING")

    detected, is_valid = classify_instrument(audio_path)
    update_generation(gen_id, detected_instrument=detected)

    if not is_valid:
        update_generation(
            gen_id,
            status        = "FAILED",
            error_message = (
                "Instrument '{}' not supported. "
                "Only piano, guitar and bass are accepted.".format(detected)
            ),
        )
        return

    # Chain to audio_worker
    celery_app.send_task(
        "audio_tasks.run_pipeline",
        args=[gen_id, audio_path, genre, mood, instrument, temperature, top_p],
        queue="audio_queue",
    )
