from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.database import get_session
from app.core.permissions import require_roles
from app.domains.auth.dependencies import get_current_user  # noqa: F401 — auth guard
from app.domains.auth.models import User
from app.domains.rbac.schemas import PermissionCreate, PermissionRead
from app.domains.rbac.services import PermissionService

router = APIRouter(prefix="/rbac/permissions", tags=["rbac"])

_svc = PermissionService()


@router.get("", response_model=list[PermissionRead])
def list_permissions(
    session: Session = Depends(get_session),
    _: object = Depends(get_current_user),
) -> list[PermissionRead]:
    return [PermissionRead.model_validate(p) for p in _svc.list_permissions(session)]


@router.post("", response_model=PermissionRead, status_code=status.HTTP_201_CREATED)
def create_permission(
    data: PermissionCreate,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN")),
) -> PermissionRead:
    try:
        perm = _svc.create_permission(session, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return PermissionRead.model_validate(perm)
