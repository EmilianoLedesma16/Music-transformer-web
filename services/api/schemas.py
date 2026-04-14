from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from models import TaskStatus


class GenerationResponse(BaseModel):
    id:                  int
    user_id:             str
    created_at:          datetime
    status:              TaskStatus
    original_filename:   str
    genre:               str
    mood:                str
    instrument:          str
    detected_instrument: Optional[str] = None
    output_xml_path:     Optional[str] = None
    output_midi_path:    Optional[str] = None
    notes_generated:     Optional[int] = None
    duration_seconds:    Optional[float] = None
    error_message:       Optional[str] = None

    model_config = {"from_attributes": True}
