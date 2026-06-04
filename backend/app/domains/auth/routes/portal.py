"""Endpoints consumidos por el portal admin.
Autenticado con service token compartido (no requiere usuario)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, col, select

from app.core.config import settings
from app.core.database import get_session
from app.domains.auth.models import User
from app.domains.rbac.models import Role

router = APIRouter(prefix="/admin", tags=["portal-admin"])


def _verify_service_token(x_service_token: str | None = Header(default=None)) -> None:
    if not x_service_token or x_service_token != settings.portal_service_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing service token",
        )


@router.get("/roles")
def list_roles(
    session: Session = Depends(get_session),
    _: None = Depends(_verify_service_token),
) -> dict:
    """Devuelve la lista de roles que esta plataforma ofrece."""
    rows = session.exec(select(Role).order_by(Role.name)).all()
    return {
        "roles": [
            {"key": r.name, "label": r.description or r.name}
            for r in rows
        ]
    }


class UsersSyncRequest(BaseModel):
    action: Literal["activate", "deactivate"]
    emails: list[str]


@router.post("/users-sync")
def users_sync(
    body: UsersSyncRequest,
    session: Session = Depends(get_session),
    _: None = Depends(_verify_service_token),
) -> dict:
    """Sincroniza el estado activo/inactivo de usuarios desde el portal.
    Llamado por id.miel al eliminar (deactivate) o restaurar (activate) un usuario.
    matched=0 es válido: el usuario aún no hizo SSO, no tiene fila local.
    """
    emails = [e.lower().strip() for e in body.emails if e]
    if not emails:
        return {"ok": True, "matched": 0}

    is_active = body.action == "activate"
    users = session.exec(select(User).where(col(User.email).in_(emails))).all()
    for user in users:
        user.is_active = is_active
        session.add(user)
    session.commit()
    return {"ok": True, "action": body.action, "matched": len(users)}
