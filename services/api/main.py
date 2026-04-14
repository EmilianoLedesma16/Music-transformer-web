import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import engine, get_db, Base
from models import Generation, TaskStatus
from schemas import GenerationResponse
from celery_app import celery_app

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Music Transformer API")

UPLOAD_DIR = Path("/app/data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

VALID_GENRES      = {"ROCK", "POP", "FUNK", "JAZZ", "LATIN", "CLASSICAL", "ELECTRONIC"}
VALID_MOODS       = {"HAPPY", "SAD", "DARK", "RELAXED", "TENSE"}
VALID_INSTRUMENTS = {"BASS", "PIANO", "GUITAR"}


@app.post("/generate", response_model=GenerationResponse)
async def generate(
    user_id:     str        = Form(...),
    genre:       str        = Form("FUNK"),
    mood:        str        = Form("HAPPY"),
    instrument:  str        = Form("BASS"),
    temperature: float      = Form(1.0),
    top_p:       float      = Form(0.9),
    audio:       UploadFile = File(...),
    db:          Session    = Depends(get_db),
):
    genre      = genre.upper()
    mood       = mood.upper()
    instrument = instrument.upper()

    if genre not in VALID_GENRES:
        raise HTTPException(status_code=422, detail=f"genre must be one of {VALID_GENRES}")
    if mood not in VALID_MOODS:
        raise HTTPException(status_code=422, detail=f"mood must be one of {VALID_MOODS}")
    if instrument not in VALID_INSTRUMENTS:
        raise HTTPException(status_code=422, detail=f"instrument must be one of {VALID_INSTRUMENTS}")

    # 1. Persist audio file
    ext       = Path(audio.filename).suffix
    job_id    = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"{job_id}{ext}"
    with open(save_path, "wb") as f:
        shutil.copyfileobj(audio.file, f)

    # 2. Create DB record
    gen = Generation(
        user_id           = user_id,
        original_filename = audio.filename,
        audio_path        = str(save_path),
        genre             = genre,
        mood              = mood,
        instrument        = instrument,
        temperature       = temperature,
        top_p             = top_p,
        status            = TaskStatus.PENDING,
    )
    db.add(gen)
    db.commit()
    db.refresh(gen)

    # 3. Dispatch to ml_worker (CNN14 validation)
    task = celery_app.send_task(
        "ml_tasks.validate_instrument",
        args=[gen.id, str(save_path), genre, mood, instrument, temperature, top_p],
        queue="ml_queue",
    )
    gen.celery_task_id = task.id
    gen.status         = TaskStatus.VALIDATING
    db.commit()
    db.refresh(gen)

    return gen


@app.get("/generation/{gen_id}", response_model=GenerationResponse)
def get_generation(gen_id: int, db: Session = Depends(get_db)):
    gen = db.query(Generation).filter(Generation.id == gen_id).first()
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found")
    return gen


@app.get("/generations/{user_id}", response_model=list[GenerationResponse])
def list_generations(user_id: str, db: Session = Depends(get_db)):
    return (
        db.query(Generation)
        .filter(Generation.user_id == user_id)
        .order_by(Generation.created_at.desc())
        .all()
    )


# Serve Basilio's frontend as static files
_frontend = Path("/app/frontend")
if _frontend.exists():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")
