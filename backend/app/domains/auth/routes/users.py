from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel
from sqlmodel import Session, func, select

from app.domains.audit.models.audit_log import AuditLog
from app.domains.audit.services import AuditService
from app.core.database import get_session
from app.core.permissions import require_roles
from app.domains.academic.models.lms_course import LmsCourse
from app.domains.academic.models.lms_course_student import LmsCourseStudent
from app.domains.academic.models.lms_grade_director import LmsGradeDirector
from app.domains.auth.dependencies import get_current_user
from app.domains.auth.models import User
from app.domains.auth.repositories import UserRepository
from app.domains.auth.schemas import UserRead
from app.domains.auth.services.user_service import UserService
from app.domains.rbac.repositories.user_role_repository import UserRoleRepository

router = APIRouter(prefix="/auth/users", tags=["auth"])

_svc = UserService()
_audit = AuditService()


class CreateUserRequest(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    phone: str | None = None
    position: str | None = None


class UpdateUserRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    position: str | None = None
    is_active: bool | None = None


class ChangePasswordRequest(BaseModel):
    new_password: str


# ── Helpers para connection-stats ─────────────────────────────────────────────

def _get_director_user_ids(session: Session, director_internal_id: int) -> list[int]:
    grade_dirs = session.exec(
        select(LmsGradeDirector).where(
            LmsGradeDirector.user_id == director_internal_id,
            LmsGradeDirector.is_active == True,
        )
    ).all()

    user_ids: set[int] = set()
    for gd in grade_dirs:
        courses = session.exec(
            select(LmsCourse).where(
                LmsCourse.grade_id == gd.grade_id,
                LmsCourse.is_active == True,
            )
        ).all()
        for course in courses:
            students = session.exec(
                select(LmsCourseStudent).where(
                    LmsCourseStudent.course_id == course.id,
                    LmsCourseStudent.is_active == True,
                )
            ).all()
            for s in students:
                user_ids.add(s.user_id)
            if course.teacher_id:
                user_ids.add(course.teacher_id)

    return list(user_ids)


def _get_connection_stats(
    session: Session,
    days: int,
    requesting_user_internal_id: int,
    filter_user_public_id: UUID | None,
) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    roles = UserRoleRepository(session).get_role_names_for_user(requesting_user_internal_id)
    is_director_only = "DIRECTOR" in roles and "ADMIN" not in roles

    allowed_user_ids: list[int] | None = None
    if is_director_only:
        allowed_user_ids = _get_director_user_ids(session, requesting_user_internal_id)

    filter_user: User | None = None
    if filter_user_public_id is not None:
        filter_user = UserRepository(session).get_by_public_id(filter_user_public_id)
        if filter_user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
        if is_director_only and filter_user.id not in (allowed_user_ids or []):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Sin acceso a ese usuario")

    # Logins por día
    day_stmt = (
        select(
            func.date(AuditLog.created_at).label("date"),
            func.count(AuditLog.id).label("logins"),
        )
        .where(AuditLog.action == "auth.login", AuditLog.created_at >= since)
    )
    if filter_user is not None:
        day_stmt = day_stmt.where(AuditLog.user_id == filter_user.id)
    elif allowed_user_ids is not None:
        day_stmt = day_stmt.where(AuditLog.user_id.in_(allowed_user_ids))
    day_stmt = day_stmt.group_by(func.date(AuditLog.created_at)).order_by("date")
    logins_by_day = session.exec(day_stmt).all()

    # Top usuarios
    top_stmt = (
        select(AuditLog.user_id, func.count(AuditLog.id).label("login_count"))
        .where(AuditLog.action == "auth.login", AuditLog.created_at >= since)
    )
    if filter_user is not None:
        top_stmt = top_stmt.where(AuditLog.user_id == filter_user.id)
    elif allowed_user_ids is not None:
        top_stmt = top_stmt.where(AuditLog.user_id.in_(allowed_user_ids))
    top_stmt = (
        top_stmt.group_by(AuditLog.user_id)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
    )

    top_users = []
    for row in session.exec(top_stmt).all():
        u = session.get(User, row.user_id)
        if u:
            top_users.append({
                "user_id": str(u.public_id),
                "name": f"{u.first_name} {u.last_name}",
                "email": u.email,
                "login_count": row.login_count,
            })

    # Logins por hora del día
    hour_stmt = (
        select(
            func.hour(AuditLog.created_at).label("hour"),
            func.count(AuditLog.id).label("logins"),
        )
        .where(AuditLog.action == "auth.login", AuditLog.created_at >= since)
    )
    if filter_user is not None:
        hour_stmt = hour_stmt.where(AuditLog.user_id == filter_user.id)
    elif allowed_user_ids is not None:
        hour_stmt = hour_stmt.where(AuditLog.user_id.in_(allowed_user_ids))
    hour_stmt = hour_stmt.group_by(func.hour(AuditLog.created_at)).order_by("hour")
    hour_map = {r.hour: r.logins for r in session.exec(hour_stmt).all()}
    logins_by_hour = [{"hour": h, "logins": hour_map.get(h, 0)} for h in range(24)]

    # Totales
    total_logins = sum(r.logins for r in logins_by_day)

    logout_stmt = select(func.count(AuditLog.id)).where(
        AuditLog.action == "auth.logout",
        AuditLog.created_at >= since,
    )
    if allowed_user_ids is not None:
        logout_stmt = logout_stmt.where(AuditLog.user_id.in_(allowed_user_ids))
    total_logouts = session.exec(logout_stmt).first() or 0

    unique_stmt = select(func.count(func.distinct(AuditLog.user_id))).where(
        AuditLog.action == "auth.login",
        AuditLog.created_at >= since,
    )
    if allowed_user_ids is not None:
        unique_stmt = unique_stmt.where(AuditLog.user_id.in_(allowed_user_ids))
    unique_users = session.exec(unique_stmt).first() or 0

    return {
        "period_days": days,
        "total_logins": total_logins,
        "total_logouts": total_logouts,
        "unique_users": unique_users,
        "logins_by_day": [{"date": str(r.date), "logins": r.logins} for r in logins_by_day],
        "logins_by_hour": logins_by_hour,
        "top_users": top_users,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/connection-stats")
def connection_stats(
    days: int = Query(default=7, ge=1, le=365),
    user_id: UUID | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "DIRECTOR")),
) -> dict:
    try:
        return _get_connection_stats(session, days, current_user.id, user_id)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))


@router.get("", response_model=list[UserRead])
def list_users(
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN")),
):
    return _svc.list_users(session)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: UUID,
    data: UpdateUserRequest,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN")),
) -> UserRead:
    user = _svc.update_user(
        session,
        public_id=user_id,
        **data.model_dump(exclude_unset=True),
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserRead.model_validate(user)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    data: CreateUserRequest,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN")),
) -> UserRead:
    try:
        user = _svc.register(
            session,
            email=data.email,
            password=data.password,
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            position=data.position,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return UserRead.model_validate(user)


@router.patch("/{user_id}/password", status_code=status.HTTP_200_OK)
def change_password(
    user_id: UUID,
    data: ChangePasswordRequest,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    try:
        _svc.change_password(
            session,
            public_id=user_id,
            new_password=data.new_password,
            current_user_public_id=current_user.public_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    _audit.log(
        session,
        user_id=current_user.id,
        action="user.password_changed",
        resource_type="user",
        resource_id=str(user_id),
        ip=request.client.host if request.client else None,
    )
    return {"message": "Password updated"}


@router.post("/import-csv", status_code=status.HTTP_200_OK)
def import_students_csv(
    file: UploadFile = File(...),
    school_id: str = Form(...),
    course_id: str = Form(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    roles = UserRoleRepository(session).get_role_names_for_user(current_user.id)
    if "ADMIN" not in [r.upper() for r in roles]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden importar usuarios",
        )

    csv_bytes = file.file.read()
    if not csv_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo está vacío",
        )

    try:
        return _svc.import_from_csv(
            session,
            csv_bytes=csv_bytes,
            school_public_id=school_id,
            course_public_id=course_id,
            requesting_user_id=current_user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
