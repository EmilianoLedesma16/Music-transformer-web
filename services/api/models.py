import enum
from sqlalchemy import Column, Integer, String, DateTime, Float, Enum, Text, ForeignKey
from sqlalchemy.sql import func
from database import Base


class TaskStatus(str, enum.Enum):
    PENDING      = "PENDING"
    VALIDATING   = "VALIDATING"
    TRANSCRIBING = "TRANSCRIBING"
    GENERATING   = "GENERATING"
    COMPLETED    = "COMPLETED"
    FAILED       = "FAILED"


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String(255), unique=True, nullable=False, index=True)
    name          = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=True)   # null para usuarios Google OAuth
    google_id     = Column(String(128), unique=True, nullable=True)
    avatar_url    = Column(String(512), nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())


class Creacion(Base):
    __tablename__ = "creaciones"

    id                  = Column(Integer, primary_key=True, index=True)
    user_id             = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), onupdate=func.now())

    # Input
    original_filename   = Column(String(255), nullable=False)
    audio_path          = Column(String(512), nullable=False)       # ruta local (volumen compartido)
    audio_input_url     = Column(String(512), nullable=True)        # URL pública en Supabase
    genre               = Column(String(32),  nullable=False)
    mood                = Column(String(32),  nullable=False)
    instrument          = Column(String(32),  nullable=False)
    temperature         = Column(Float,       default=0.9)
    top_p               = Column(Float,       default=0.9)

    # Estado de procesamiento
    status              = Column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)
    celery_task_id      = Column(String(128), nullable=True)
    detected_instrument = Column(String(64),  nullable=True)
    midi_path           = Column(String(512), nullable=True)        # ruta local MIDI intermedio

    # Salidas (URLs de Supabase)
    midi_output_url     = Column(String(512), nullable=True)
    xml_output_url      = Column(String(512), nullable=True)
    notes_generated     = Column(Integer,     nullable=True)
    duration_seconds    = Column(Float,       nullable=True)

    # Error
    error_message       = Column(Text, nullable=True)
