from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.database import get_session
from app.core.permissions import require_roles
from app.domains.auth.dependencies import get_current_user
from app.domains.auth.models import User
from app.domains.auth.repositories import UserRepository
from app.domains.rbac.repositories import RoleRepository, UserRoleRepository
from app.domains.rbac.schemas import RoleRead
from app.domains.rbac.services import RoleService, UserRoleService

router = APIRouter(prefix="/rbac/users", tags=["rbac"])

_svc = UserRoleService()
_role_svc = RoleService()


@router.get("/{user_id}/roles", response_model=list[RoleRead])
def list_user_roles(
    user_id: UUID,
    session: Session = Depends(get_session),
    _: object = Depends(get_current_user),
) -> list[RoleRead]:
    user = UserRepository(session).get_by_public_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    ur_repo = UserRoleRepository(session)
    role_repo = RoleRepository(session)
    roles = []
    for ur in ur_repo.list_by_user_id(user.id):
        r = role_repo.get_by_id(ur.role_id)
        if r:
            roles.append(RoleRead.model_validate(r))
    return roles


@router.post("/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def assign_role_to_user(
    user_id: UUID,
    role_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN")),
) -> None:
    user = UserRepository(session).get_by_public_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    role = _role_svc.get_role(session, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    try:
        _svc.assign_role_to_user(session, user.id, role.id, performed_by_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.delete("/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_role_from_user(
    user_id: UUID,
    role_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN")),
) -> None:
    user = UserRepository(session).get_by_public_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    role = _role_svc.get_role(session, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    removed = _svc.remove_role_from_user(
        session, user.id, role.id, performed_by_id=current_user.id
    )
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found"
        )


@router.get("/{user_id}/permissions", response_model=list[str])
def get_user_permissions(
    user_id: UUID,
    session: Session = Depends(get_session),
    _: object = Depends(get_current_user),
) -> list[str]:
    user = UserRepository(session).get_by_public_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _svc.get_permissions_for_user(session, user.id)
