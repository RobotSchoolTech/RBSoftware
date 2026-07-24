from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.database import get_session
from app.core.permissions import require_roles
from app.domains.auth.dependencies import get_current_user
from app.domains.auth.models import User
from app.domains.rbac.repositories import PermissionRepository, RolePermissionRepository
from app.domains.rbac.schemas import PermissionRead, RoleCreate, RoleRead
from app.domains.rbac.services import PermissionService, RolePermissionService, RoleService

router = APIRouter(prefix="/rbac/roles", tags=["rbac"])

_role_svc = RoleService()
_rp_svc = RolePermissionService()
_perm_svc = PermissionService()


# ── Roles ──────────────────────────────────────────────────────────────────────


@router.get("", response_model=list[RoleRead])
def list_roles(
    session: Session = Depends(get_session),
    _: object = Depends(get_current_user),
) -> list[RoleRead]:
    roles = _role_svc.list_roles(session)
    rp_repo = RolePermissionRepository(session)
    counts: dict[int, int] = defaultdict(int)
    for rp in rp_repo.list():
        counts[rp.role_id] += 1
    return [
        RoleRead.model_validate(r).model_copy(update={"permission_count": counts.get(r.id, 0)})
        for r in roles
    ]


@router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
def create_role(
    data: RoleCreate,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN")),
) -> RoleRead:
    try:
        role = _role_svc.create_role(session, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return RoleRead.model_validate(role)


@router.get("/{role_id}/permissions", response_model=list[PermissionRead])
def list_role_permissions(
    role_id: UUID,
    session: Session = Depends(get_session),
    _: object = Depends(get_current_user),
) -> list[PermissionRead]:
    role = _role_svc.get_role(session, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    rp_repo = RolePermissionRepository(session)
    perm_repo = PermissionRepository(session)
    perms = []
    for rp in rp_repo.list_by_role_id(role.id):
        p = perm_repo.get_by_id(rp.permission_id)
        if p:
            perms.append(PermissionRead.model_validate(p))
    return perms


@router.delete(
    "/{public_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_role(
    public_id: UUID,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN")),
) -> None:
    deleted = _role_svc.delete_role(session, public_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")


# ── Role → Permission assignments ─────────────────────────────────────────────


@router.post(
    "/{role_id}/permissions/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def assign_permission_to_role(
    role_id: UUID,
    permission_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN")),
) -> None:
    role = _role_svc.get_role(session, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    permissions = _perm_svc.list_permissions(session)
    perm = next((p for p in permissions if p.public_id == permission_id), None)
    if perm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found"
        )

    try:
        _rp_svc.assign_permission_to_role(
            session, role.id, perm.id, performed_by_id=current_user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.delete(
    "/{role_id}/permissions/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def remove_permission_from_role(
    role_id: UUID,
    permission_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN")),
) -> None:
    role = _role_svc.get_role(session, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    permissions = _perm_svc.list_permissions(session)
    perm = next((p for p in permissions if p.public_id == permission_id), None)
    if perm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found"
        )

    removed = _rp_svc.remove_permission_from_role(
        session, role.id, perm.id, performed_by_id=current_user.id
    )
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )
