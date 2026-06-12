from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_session
from app.core.permissions import require_roles
from app.core.security import hash_password
from app.domains.auth.models import User
from app.domains.auth.models.password_reset_token import PasswordResetToken
from app.domains.auth.repositories import UserRepository
from app.domains.auth.schemas import UserUpdate
from app.domains.auth.services.refresh_token_service import RefreshTokenService
from app.domains.email.email_service import EmailService

router = APIRouter(prefix="/auth/password-reset", tags=["auth"])

_TOKEN_TTL_HOURS = 48
_MIN_PASSWORD_LEN = 8


class GenerateRequest(BaseModel):
    user_id: UUID


class ConfirmRequest(BaseModel):
    token: str
    new_password: str


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _invalidate_previous_tokens(session: Session, user_id: int) -> None:
    previous = session.exec(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used == False,  # noqa: E712
        )
    ).all()
    for tok in previous:
        tok.used = True
        session.add(tok)


def _issue_token(session: Session, user: User) -> str:
    """Genera, persiste y devuelve un token raw de reset para el usuario dado."""
    _invalidate_previous_tokens(session, user.id)
    raw_token = secrets.token_urlsafe(32)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=_TOKEN_TTL_HOURS),
    )
    session.add(reset_token)
    session.commit()
    return raw_token


# ── Endpoint 1: Generar token + enviar credenciales (ADMIN) ───────────────────

@router.post("/generate", status_code=status.HTTP_200_OK)
async def generate_reset(
    data: GenerateRequest,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN")),
) -> dict[str, str]:
    user = UserRepository(session).get_by_public_id(data.user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")

    raw_token = _issue_token(session, user)
    reset_link = f"{settings.frontend_base_url}/set-password?token={raw_token}"

    await EmailService().send_credentials(
        to_email=user.email,
        first_name=user.first_name,
        username=user.email,
        reset_link=reset_link,
    )
    return {"message": "Credenciales enviadas"}


# ── Endpoint 2: Validar token (público) ───────────────────────────────────────

@router.get("/validate/{token}", status_code=status.HTTP_200_OK)
def validate_reset(
    token: str,
    session: Session = Depends(get_session),
) -> dict:
    reset_token = session.exec(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == _hash_token(token),
            PasswordResetToken.used == False,  # noqa: E712
            PasswordResetToken.expires_at > datetime.now(timezone.utc),
        )
    ).first()
    if reset_token is None:
        return {"valid": False}

    user = session.get(User, reset_token.user_id)
    if user is None:
        return {"valid": False}
    return {"valid": True, "email": user.email}


# ── Endpoint 3: Confirmar nueva contraseña (público) ──────────────────────────

@router.post("/confirm", status_code=status.HTTP_200_OK)
def confirm_reset(
    data: ConfirmRequest,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    reset_token = session.exec(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == _hash_token(data.token),
            PasswordResetToken.used == False,  # noqa: E712
            PasswordResetToken.expires_at > datetime.now(timezone.utc),
        )
    ).first()
    if reset_token is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Token inválido o expirado")

    if len(data.new_password) < _MIN_PASSWORD_LEN:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"La contraseña debe tener mínimo {_MIN_PASSWORD_LEN} caracteres",
        )

    user = session.get(User, reset_token.user_id)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Token inválido o expirado")

    repo = UserRepository(session)
    repo.update(user, UserUpdate(password_hash=hash_password(data.new_password)))

    reset_token.used = True
    session.add(reset_token)
    session.commit()

    # Invalidar sesiones previas: tras establecer contraseña por reset, las sesiones
    # antiguas dejan de ser válidas.
    RefreshTokenService().revoke_all_for_user(session, user.id)

    return {"message": "Contraseña establecida"}
