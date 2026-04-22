"""
ByteBeat API — FastAPI
Endpoints:
  POST /auth/register          registro con email+password
  POST /auth/login             login con email+password
  GET  /auth/google            iniciar Google OAuth
  GET  /auth/google/callback   callback Google OAuth

  GET  /me                     perfil del usuario autenticado
  POST /parse-prompt           texto libre → parámetros musicales (NLP)
  POST /process                subir audio → iniciar job
  GET  /process/{job_id}       polling de estado
  GET  /creaciones             listar creaciones del usuario
  DELETE /creaciones/{id}      borrar creacion + archivos Supabase
"""
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Annotated, Optional

from fastapi import (
    Depends, FastAPI, File, Form, Header, HTTPException, UploadFile,
)
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from auth.router import router as auth_router
from auth.jwt import decode_token
from celery_app import celery_app
from database import Base, engine, get_db
from models import Creacion, TaskStatus, User
from prompt_parser import parse_prompt
from schemas import CreacionResponse, UserResponse
from storage.supabase_client import delete_file, path_from_url, upload_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ByteBeat API", version="1.0.0")
app.include_router(auth_router)

UPLOAD_DIR = Path("/app/data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

VALID_GENRES      = {"ROCK", "POP", "FUNK", "JAZZ", "LATIN", "CLASSICAL", "ELECTRONIC"}
VALID_MOODS       = {"HAPPY", "SAD", "DARK", "RELAXED", "TENSE"}
VALID_ENERGIES    = {"LOW", "MED", "HIGH"}
VALID_INSTRUMENTS = {"BASS", "PIANO", "GUITAR"}
VALID_EXTENSIONS  = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}


# ── Auth dependencies ─────────────────────────────────────────────────────────

async def get_current_user(
    authorization: Annotated[Optional[str], Header()] = None,
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticado")
    user_id = decode_token(authorization[7:])
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Requiere rol de administrador")
    return current_user


# ── Endpoints auxiliares ──────────────────────────────────────────────────────

@app.get("/me", response_model=UserResponse, summary="Perfil del usuario autenticado")
def me(current_user: User = Depends(get_current_user)):
    return current_user


@app.post("/parse-prompt", summary="Texto libre → parámetros musicales")
def parse_prompt_endpoint(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    text = body.get("text", "")
    result = parse_prompt(text)
    return {
        "genre":      result.genre,
        "mood":       result.mood,
        "energy":     result.energy,
        "instrument": result.instrument,
        "confidence": round(result.confidence, 2),
        "detected":   result.detected,
    }


# ── Admin endpoints ───────────────────────────────────────────────────────────

@app.get("/admin/users", response_model=list[UserResponse], summary="Listar todos los usuarios (admin)")
def admin_list_users(
    _admin: User    = Depends(require_admin),
    db:     Session = Depends(get_db),
):
    return db.query(User).order_by(User.created_at.desc()).all()


@app.patch("/admin/users/{user_id}/role", summary="Cambiar rol de usuario (admin)")
def admin_set_role(
    user_id: int,
    body:    dict,
    _admin:  User    = Depends(require_admin),
    db:      Session = Depends(get_db),
):
    role = body.get("role", "").lower()
    if role not in {"user", "admin"}:
        raise HTTPException(422, "role debe ser 'user' o 'admin'")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    user.role = role
    db.commit()
    return {"id": user_id, "role": role}


# ── Endpoints principales ─────────────────────────────────────────────────────

@app.post("/process", response_model=CreacionResponse, summary="Subir audio e iniciar generación")
async def process(
    genre:       str        = Form("POP"),
    mood:        str        = Form("HAPPY"),
    energy:      str        = Form("MED"),
    instrument:  str        = Form("GUITAR"),
    temperature: float      = Form(0.9),
    top_p:       float      = Form(0.9),
    audio:       UploadFile = File(...),
    current_user: User      = Depends(get_current_user),
    db:           Session   = Depends(get_db),
):
    genre      = genre.upper()
    mood       = mood.upper()
    energy     = energy.upper()
    instrument = instrument.upper()

    if genre not in VALID_GENRES:
        raise HTTPException(422, f"genre debe ser uno de {sorted(VALID_GENRES)}")
    if mood not in VALID_MOODS:
        raise HTTPException(422, f"mood debe ser uno de {sorted(VALID_MOODS)}")
    if energy not in VALID_ENERGIES:
        raise HTTPException(422, f"energy debe ser uno de {sorted(VALID_ENERGIES)}")
    if instrument not in VALID_INSTRUMENTS:
        raise HTTPException(422, f"instrument debe ser uno de {sorted(VALID_INSTRUMENTS)}")

    ext = Path(audio.filename or "audio.wav").suffix.lower()
    if ext not in VALID_EXTENSIONS:
        raise HTTPException(422, f"El audio debe ser {VALID_EXTENSIONS}")

    # 1. Guardar localmente en el volumen compartido
    job_id     = str(uuid.uuid4())
    local_path = UPLOAD_DIR / f"{job_id}{ext}"
    with open(local_path, "wb") as f:
        shutil.copyfileobj(audio.file, f)

    # 2. Subir a Supabase (no bloquea si falla)
    audio_url = upload_file(
        str(local_path),
        f"users/{current_user.id}/audio/{job_id}{ext}",
        "audio/mpeg",
    )

    # 3. Crear registro en BD
    creacion = Creacion(
        user_id           = current_user.id,
        original_filename = audio.filename or local_path.name,
        audio_path        = str(local_path),
        audio_input_url   = audio_url,
        genre             = genre,
        mood              = mood,
        energy            = energy,
        instrument        = instrument,
        temperature       = temperature,
        top_p             = top_p,
        status            = TaskStatus.PENDING,
    )
    db.add(creacion)
    db.commit()
    db.refresh(creacion)

    # 4. Despachar al ml_worker (validación CNN14)
    task = celery_app.send_task(
        "ml_tasks.validate_instrument",
        args=[creacion.id, str(local_path), genre, mood, energy, instrument, temperature, top_p],
        queue="ml_queue",
    )
    creacion.celery_task_id = task.id
    creacion.status         = TaskStatus.VALIDATING
    db.commit()
    db.refresh(creacion)

    logger.info("Creacion %d despachada → ml_queue (task %s)", creacion.id, task.id)
    return creacion


@app.get("/process/{job_id}", response_model=CreacionResponse, summary="Polling de estado")
def get_job(
    job_id: int,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    creacion = db.query(Creacion).filter(
        Creacion.id == job_id,
        Creacion.user_id == current_user.id,
    ).first()
    if not creacion:
        raise HTTPException(404, "Creacion no encontrada")
    return creacion


@app.get("/creaciones", response_model=list[CreacionResponse], summary="Listar mis creaciones")
def list_creaciones(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    return (
        db.query(Creacion)
        .filter(Creacion.user_id == current_user.id)
        .order_by(Creacion.created_at.desc())
        .all()
    )


@app.delete("/creaciones/{creacion_id}", status_code=204, summary="Borrar creacion y archivos")
def delete_creacion(
    creacion_id:  int,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    creacion = db.query(Creacion).filter(
        Creacion.id == creacion_id,
        Creacion.user_id == current_user.id,
    ).first()
    if not creacion:
        raise HTTPException(404, "Creacion no encontrada")

    for url in [creacion.audio_input_url, creacion.midi_output_url, creacion.xml_output_url]:
        sp = path_from_url(url) if url else None
        if sp:
            delete_file(sp)

    db.delete(creacion)
    db.commit()


# ── Frontend estático ─────────────────────────────────────────────────────────
_frontend = Path("/app/frontend")
if _frontend.exists():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")
