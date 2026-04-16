import os
import bcrypt as _bcrypt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import UserCreate, UserLogin, TokenResponse, UserResponse
from auth.jwt import create_access_token
from auth.google_oauth import get_google_auth_url, exchange_code

router   = APIRouter(prefix="/auth", tags=["auth"])
FRONTEND = os.environ.get("FRONTEND_URL", "http://localhost:8000")


def _hash(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def _verify(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


@router.post("/register", response_model=TokenResponse, summary="Registro con email y contraseña")
async def register(body: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=409, detail="El email ya está registrado")
    user = User(
        email=body.email,
        name=body.name,
        password_hash=_hash(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(
        access_token=create_access_token(user.id),
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse, summary="Login con email y contraseña")
async def login(body: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not user.password_hash or not _verify(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    return TokenResponse(
        access_token=create_access_token(user.id),
        user=UserResponse.model_validate(user),
    )


@router.get("/google", summary="Iniciar login con Google OAuth")
async def google_login():
    return RedirectResponse(get_google_auth_url())


@router.get("/google/callback", summary="Callback de Google OAuth")
async def google_callback(code: str, db: Session = Depends(get_db)):
    try:
        google_user = await exchange_code(code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error en Google OAuth: {e}")

    email     = google_user["email"]
    google_id = google_user.get("sub", "")
    name      = google_user.get("name")
    picture   = google_user.get("picture")

    user = db.query(User).filter(User.email == email).first()
    if user:
        if not user.google_id:
            user.google_id  = google_id
            user.avatar_url = picture
            db.commit()
    else:
        user = User(email=email, name=name, google_id=google_id, avatar_url=picture)
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token(user.id)
    return RedirectResponse(f"{FRONTEND}/dashboard.html?token={token}")
