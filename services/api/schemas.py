from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class UserCreate(BaseModel):
    email: str
    password: str
    name: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str = "user"
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class CreacionResponse(BaseModel):
    id: int
    user_id: int
    original_filename: str
    audio_input_url: Optional[str] = None
    genre: str
    mood: str
    energy: str = "MED"
    instrument: str
    temperature: float
    top_p: float
    status: str
    detected_instrument: Optional[str] = None
    midi_output_url: Optional[str] = None
    xml_output_url: Optional[str] = None
    notes_generated: Optional[int] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    progress_detail: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
