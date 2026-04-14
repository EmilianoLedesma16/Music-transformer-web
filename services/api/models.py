import enum
from sqlalchemy import Column, Integer, String, DateTime, Float, Enum, Text
from sqlalchemy.sql import func
from database import Base


class TaskStatus(str, enum.Enum):
    PENDING      = "PENDING"
    VALIDATING   = "VALIDATING"
    TRANSCRIBING = "TRANSCRIBING"
    GENERATING   = "GENERATING"
    COMPLETED    = "COMPLETED"
    FAILED       = "FAILED"


class Generation(Base):
    __tablename__ = "generations"

    id                  = Column(Integer, primary_key=True, index=True)
    user_id             = Column(String(64),  nullable=False, index=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), onupdate=func.now())

    # Input
    original_filename   = Column(String(255), nullable=False)
    audio_path          = Column(String(512), nullable=False)
    genre               = Column(String(32),  nullable=False)
    mood                = Column(String(32),  nullable=False)
    instrument          = Column(String(32),  nullable=False)
    temperature         = Column(Float,       default=1.0)
    top_p               = Column(Float,       default=0.9)

    # Processing state
    status              = Column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)
    celery_task_id      = Column(String(128), nullable=True)
    detected_instrument = Column(String(64),  nullable=True)
    midi_path           = Column(String(512), nullable=True)

    # Output
    output_midi_path    = Column(String(512), nullable=True)
    output_xml_path     = Column(String(512), nullable=True)
    notes_generated     = Column(Integer,     nullable=True)
    duration_seconds    = Column(Float,       nullable=True)

    # Error
    error_message       = Column(Text, nullable=True)
