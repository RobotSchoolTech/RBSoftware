"""Endpoints consumidos por el portal admin para enumerar roles disponibles
en el LMS. Autenticado con service token compartido (no requiere usuario)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_session
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
    """Devuelve la lista de roles que esta plataforma ofrece.
    Consumido por el portal-admin para llenar el select de la columna LMS.
    """
    rows = session.exec(select(Role).order_by(Role.name)).all()
    return {
        "roles": [
            {"key": r.name, "label": r.description or r.name}
            for r in rows
        ]
    }
