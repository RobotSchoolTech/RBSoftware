from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from sqlmodel import Session

from app.core.config import settings
from app.core.database import get_session
from app.core.security import create_access_token
from app.domains.audit.services import AuditService
from app.domains.auth.models import User
from app.domains.auth.repositories import UserRepository
from app.domains.auth.routes.auth import _set_auth_cookies
from app.domains.auth.services.refresh_token_service import RefreshTokenService
from app.domains.rbac.repositories import UserRoleRepository
from app.domains.rbac.repositories import RoleRepository
from app.domains.rbac.schemas import UserRoleCreate

router = APIRouter(prefix="/auth/sso", tags=["auth"])

_audit = AuditService()
_jwks_cache: dict | None = None

# Mapeo de grupos Authentik → roles internos del LMS
_GROUP_TO_ROLE: dict[str, str] = {
    "admin":            "ADMIN",
    "authentik Admins": "ADMIN",
    "director":         "DIRECTOR",
    "trainer":          "TRAINER",
    "teacher":          "TEACHER",
    "student":          "STUDENT",
}


def _sync_roles_from_groups(
    session: Session,
    user_id: int,
    groups: list[str],
    user_role_repo: UserRoleRepository,
    role_repo: RoleRepository,
) -> list[str]:
    """Agrega al usuario los roles LMS que correspondan a sus grupos de Authentik.
    No elimina roles existentes (comportamiento seguro durante la transición)."""
    target = {_GROUP_TO_ROLE[g] for g in groups if g in _GROUP_TO_ROLE}
    current = set(user_role_repo.get_role_names_for_user(user_id))
    for role_name in target - current:
        role = role_repo.get_by_name(role_name)
        if role:
            user_role_repo.create(UserRoleCreate(user_id=user_id, role_id=role.id))
    return list(current | target)


async def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    jwks_url = f"{settings.authentik_url}/application/o/{settings.authentik_client_id}/jwks/"
    async with httpx.AsyncClient() as client:
        res = await client.get(jwks_url, timeout=10)
        res.raise_for_status()
    _jwks_cache = res.json()
    return _jwks_cache


def _validate_token(token: str, jwks: dict) -> dict:
    try:
        claims = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.authentik_client_id,
            options={"verify_at_hash": False},
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {exc}",
        )
    return claims


class _SSORequest:
    def __init__(self, token: str): ...


from pydantic import BaseModel


class SSOTokenRequest(BaseModel):
    token: str


@router.post("/login", response_model=dict)
async def sso_login(
    request: Request,
    body: SSOTokenRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> dict:
    ip = request.client.host if request.client else None

    try:
        jwks = await _get_jwks()
        claims = _validate_token(body.token, jwks)
    except HTTPException:
        _jwks_cache = None  # forzar refetch en próximo intento
        raise

    email: str | None = claims.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El token no contiene email",
        )

    user: User | None = UserRepository(session).get_by_email(email)
    if user is None or not user.is_active:
        _audit.log(
            session,
            user_id=None,
            action="auth.sso_failed",
            resource_type="user",
            resource_id=email,
            ip=ip,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario no encontrado en el LMS",
        )

    groups: list[str] = claims.get("groups", [])
    user_role_repo = UserRoleRepository(session)
    role_names = _sync_roles_from_groups(
        session, user.id, groups, user_role_repo, RoleRepository(session)
    )

    raw_refresh, _ = RefreshTokenService().create_token(session, user.id)
    access_token = create_access_token({"sub": str(user.public_id)})
    _set_auth_cookies(response, access_token, raw_refresh, role_names)

    _audit.log(
        session,
        user_id=user.id,
        action="auth.sso_login",
        resource_type="user",
        resource_id=str(user.public_id),
        ip=ip,
    )

    return {"ok": True}
