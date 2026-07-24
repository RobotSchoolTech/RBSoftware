from __future__ import annotations

import json

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlmodel import Session

from app.core.database import get_session
from app.core.security import create_access_token
from app.domains.audit.services import AuditService
from app.domains.auth.dependencies import get_current_user, get_current_user_optional
from app.domains.auth.models import User
from app.domains.auth.schemas import UserRead
from app.domains.auth.services.refresh_token_service import RefreshTokenService
from app.domains.auth.services.user_service import UserService
from app.domains.rbac.repositories import UserRoleRepository
from app.domains.rbac.services import UserRoleService

router = APIRouter(prefix="/auth", tags=["auth"])

_ACCESS_COOKIE = "access_token"
_REFRESH_COOKIE = "refresh_token"
_ROLES_COOKIE = "user_roles"
_audit = AuditService()


class LoginRequest(BaseModel):
    email: str
    password: str


def _set_auth_cookies(
    response: Response, access_token: str, refresh_token: str, role_names: list[str],
) -> None:
    response.set_cookie(key=_ACCESS_COOKIE, value=access_token, httponly=True, samesite="lax")
    response.set_cookie(key=_REFRESH_COOKIE, value=refresh_token, httponly=True, samesite="lax")
    response.set_cookie(
        key=_ROLES_COOKIE,
        value=json.dumps(role_names),
        httponly=False,
        samesite="lax",
        path="/",
    )


def _delete_auth_cookies(response: Response) -> None:
    response.delete_cookie(_ACCESS_COOKIE)
    response.delete_cookie(_REFRESH_COOKIE)
    response.delete_cookie(_ROLES_COOKIE, path="/")


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/login", response_model=UserRead)
def login(
    request: Request,
    data: LoginRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> UserRead:
    ip = _client_ip(request)
    user = UserService().authenticate(session, data.email, data.password)
    if user is None:
        _audit.log(
            session,
            user_id=None,
            action="auth.login_failed",
            resource_type="user",
            resource_id=data.email,
            ip=ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    raw_refresh, _ = RefreshTokenService().create_token(session, user.id)
    access_token = create_access_token({"sub": str(user.public_id)})
    role_names = UserRoleRepository(session).get_role_names_for_user(user.id)
    _set_auth_cookies(response, access_token, raw_refresh, role_names)
    _audit.log(
        session,
        user_id=user.id,
        action="auth.login",
        resource_type="user",
        resource_id=str(user.public_id),
        ip=ip,
    )
    return UserRead.model_validate(user).model_copy(update={"roles": role_names})


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def logout(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    current_user: User | None = Depends(get_current_user_optional),
    session: Session = Depends(get_session),
) -> None:
    if refresh_token:
        RefreshTokenService().revoke(session, refresh_token)
    _delete_auth_cookies(response)
    _audit.log(
        session,
        user_id=current_user.id if current_user else None,
        action="auth.logout",
        resource_type="user",
        resource_id=str(current_user.public_id) if current_user else "",
        ip=_client_ip(request),
    )


@router.post("/refresh", response_model=UserRead)
def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    session: Session = Depends(get_session),
) -> UserRead:
    ip = _client_ip(request)
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
        )
    result = RefreshTokenService().validate_and_rotate(session, refresh_token)
    if result is None:
        _delete_auth_cookies(response)
        _audit.log(
            session,
            user_id=None,
            action="auth.refresh_failed",
            resource_type="refresh_token",
            resource_id="",
            ip=ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    raw_new_refresh, record = result
    user = UserService().get_by_id(session, record.user_id)
    if user is None or not user.is_active:
        _delete_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    new_access_token = create_access_token({"sub": str(user.public_id)})
    role_names = UserRoleRepository(session).get_role_names_for_user(user.id)
    _set_auth_cookies(response, new_access_token, raw_new_refresh, role_names)
    return UserRead.model_validate(user).model_copy(update={"roles": role_names})


@router.get("/me", response_model=UserRead)
def me(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserRead:
    roles = UserRoleService().get_roles_for_user(session, current_user.id)
    role_names = [r.name for r in roles]
    return UserRead.model_validate(current_user).model_copy(update={"roles": role_names})
