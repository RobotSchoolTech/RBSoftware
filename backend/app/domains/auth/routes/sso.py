from __future__ import annotations

import logging
import secrets
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlmodel import Session

from app.core.config import settings
from app.core.database import get_session
from app.core.security import create_access_token, hash_password
from app.domains.audit.services import AuditService
from app.domains.auth.models import User
from app.domains.auth.repositories import UserRepository
from app.domains.auth.routes.auth import _set_auth_cookies
from app.domains.auth.schemas import UserCreate
from app.domains.auth.services.refresh_token_service import RefreshTokenService
from app.domains.rbac.repositories import RoleRepository, UserRoleRepository
from app.domains.rbac.schemas import UserRoleCreate

router = APIRouter(prefix="/auth/sso", tags=["auth"])

_PLATFORM_KEY = "lms"  # clave de esta plataforma en el claim 'platforms' del JWT
_ROLE_NONE = "__none__"

_audit = AuditService()
_log = logging.getLogger(__name__)
_jwks_cache: list[dict] = []
_jwks_cache_at: float = 0.0


async def _get_jwks() -> list[dict]:
    global _jwks_cache, _jwks_cache_at
    if not _jwks_cache or time.monotonic() - _jwks_cache_at > 3600:
        async with httpx.AsyncClient() as client:
            res = await client.get(settings.jwt_jwks_url, timeout=10)
            res.raise_for_status()
        _jwks_cache = res.json().get("keys", [])
        _jwks_cache_at = time.monotonic()
    return _jwks_cache


def _validate_token(token: str, jwks: list[dict]) -> dict:
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        key = next((k for k in jwks if k.get("kid") == kid), jwks[0] if jwks else None)
        if not key:
            raise JWTError("no matching key in JWKS")
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            options={"verify_aud": False, "verify_at_hash": False},
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {exc}",
        )
    return claims


def _sync_role(session: Session, user_id: int, role_key: str) -> list[str]:
    """Sincroniza los user_roles del usuario para que sea EXACTAMENTE [role_key].

    El portal admin es la única fuente de verdad: si llega TEACHER pero el user
    tenía TRAINER, se reemplaza. Devuelve la lista de roles resultante.
    """
    role_repo = RoleRepository(session)
    user_role_repo = UserRoleRepository(session)
    role = role_repo.get_by_name(role_key)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rol '{role_key}' inexistente en LMS — sincronizar con portal admin",
        )
    user_role_repo.set_user_roles(user_id, [role.id])
    return [role.name]


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
        _jwks_cache.clear()
        raise

    email = (claims.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token sin email")

    platforms = claims.get("platforms") or {}
    role_key = platforms.get(_PLATFORM_KEY)
    if not role_key or role_key == _ROLE_NONE:
        try:
            _audit.log(session, user_id=None, action="auth.sso_no_access",
                       resource_type="user", resource_id=email, ip=ip)
        except Exception:
            _log.exception("audit sso_no_access failed")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Sin acceso al LMS")

    user_repo = UserRepository(session)
    user: User | None = user_repo.get_by_email(email)

    if user is None:
        name = (claims.get("name") or email).strip()
        parts = name.split(" ", 1)
        first, last = parts[0], parts[1] if len(parts) > 1 else ""
        user = user_repo.create(UserCreate(
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            first_name=first,
            last_name=last,
        ))

    if not user.is_active:
        try:
            _audit.log(session, user_id=user.id, action="auth.sso_blocked",
                       resource_type="user", resource_id=email, ip=ip)
        except Exception:
            _log.exception("audit sso_blocked failed")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cuenta inactiva")

    role_names = _sync_role(session, user.id, role_key)

    raw_refresh, _ = RefreshTokenService().create_token(session, user.id)
    access_token = create_access_token({"sub": str(user.public_id)})
    _set_auth_cookies(response, access_token, raw_refresh, role_names)

    try:
        _audit.log(session, user_id=user.id, action="auth.sso_login",
                   resource_type="user", resource_id=str(user.public_id), ip=ip)
    except Exception:
        _log.exception("audit sso_login failed")

    return {"ok": True}
