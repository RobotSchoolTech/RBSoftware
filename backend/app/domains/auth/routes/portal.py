"""Endpoints consumidos por el portal admin.
Autenticado con service token compartido (no requiere usuario)."""
from __future__ import annotations

import secrets
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, col, select

from app.core.config import settings
from app.core.database import get_session
from app.core.security import hash_password
from app.domains.academic.models.lms_grade import LmsGrade
from app.domains.academic.repositories.course_repository import CourseRepository
from app.domains.academic.repositories.course_student_repository import CourseStudentRepository
from app.domains.academic.repositories.grade_repository import GradeRepository
from app.domains.academic.repositories.school_repository import SchoolRepository
from app.domains.academic.repositories.school_teacher_repository import SchoolTeacherRepository
from app.domains.auth.models import User
from app.domains.auth.schemas import UserCreate
from app.domains.rbac.models import Role
from app.domains.rbac.repositories import RoleRepository, UserRoleRepository

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


@router.get("/schools")
def list_schools_for_portal(
    session: Session = Depends(get_session),
    _: None = Depends(_verify_service_token),
) -> dict:
    schools = SchoolRepository(session).list()
    return {
        "schools": [
            {"public_id": str(s.public_id), "name": s.name, "work_line": s.work_line}
            for s in schools
        ]
    }


@router.get("/schools/{school_public_id}/grades")
def list_grades_for_portal(
    school_public_id: UUID,
    session: Session = Depends(get_session),
    _: None = Depends(_verify_service_token),
) -> dict:
    school = SchoolRepository(session).get_by_public_id(school_public_id)
    if school is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "School not found")
    grades = GradeRepository(session).list_by_school(school.id)
    return {
        "grades": [
            {"public_id": str(g.public_id), "name": g.name}
            for g in grades if g.is_active
        ]
    }


@router.get("/schools/{school_public_id}/courses")
def list_courses_for_portal(
    school_public_id: UUID,
    session: Session = Depends(get_session),
    _: None = Depends(_verify_service_token),
) -> dict:
    school = SchoolRepository(session).get_by_public_id(school_public_id)
    if school is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "School not found")
    courses = CourseRepository(session).list_by_school(school.id)
    grade_ids = list({c.grade_id for c in courses})
    grade_map: dict[int, str] = {}
    if grade_ids:
        grades = session.exec(select(LmsGrade).where(LmsGrade.id.in_(grade_ids))).all()
        grade_map = {g.id: g.name for g in grades}
    return {
        "courses": [
            {
                "public_id": str(c.public_id),
                "name": c.name,
                "grade_name": grade_map.get(c.grade_id, ""),
            }
            for c in courses
        ]
    }


@router.get("/schools/{school_public_id}/teachers")
def list_teachers_for_portal(
    school_public_id: UUID,
    session: Session = Depends(get_session),
    _: None = Depends(_verify_service_token),
) -> dict:
    school = SchoolRepository(session).get_by_public_id(school_public_id)
    if school is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "School not found")
    # school_teachers es la tabla de MEMBRESÍA al colegio: contiene docentes y
    # estudiantes. Filtrar por rol TEACHER, igual que AcademicService.
    members = SchoolTeacherRepository(session).list_teachers(school.id)
    role_repo = UserRoleRepository(session)
    teachers = []
    for u in members:
        role_names = role_repo.get_role_names_for_user(u.id)
        if "TEACHER" not in role_names:
            continue
        teachers.append(
            {
                "public_id": str(u.public_id),
                "name": f"{u.first_name} {u.last_name}".strip() or u.email,
                "email": u.email,
                "roles": role_names,
            }
        )
    return {"teachers": teachers}


class UsersSyncRequest(BaseModel):
    action: Literal["activate", "deactivate", "upsert"]
    emails: list[str] = []
    # upsert only
    email: str | None = None
    name: str | None = None
    role: str | None = None
    course_public_id: str | None = None
    grade_public_id: str | None = None


@router.post("/users-sync")
def users_sync(
    body: UsersSyncRequest,
    session: Session = Depends(get_session),
    _: None = Depends(_verify_service_token),
) -> dict:
    """Sincroniza usuarios desde el portal:
    - activate/deactivate: activa o desactiva por lista de emails.
    - upsert: pre-crea el usuario si no existe y sincroniza su rol.
    """
    if body.action == "upsert":
        return _handle_upsert(session, body)
    return _handle_toggle(session, body)


def _handle_toggle(session: Session, body: UsersSyncRequest) -> dict:
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


def _handle_upsert(session: Session, body: UsersSyncRequest) -> dict:
    email = (body.email or "").lower().strip()
    if not email:
        raise HTTPException(status_code=422, detail="email requerido para upsert")

    user = session.exec(select(User).where(User.email == email)).first()
    created = False
    if user is None:
        name = (body.name or email).strip()
        parts = name.split(" ", 1)
        first, last = parts[0], parts[1] if len(parts) > 1 else ""
        user = User.model_validate(UserCreate(
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            first_name=first,
            last_name=last,
        ))
        session.add(user)
        session.commit()
        session.refresh(user)
        created = True

    if body.role:
        role = RoleRepository(session).get_by_name(body.role)
        if role:
            UserRoleRepository(session).set_user_roles(user.id, [role.id])

    if body.course_public_id:
        try:
            course = CourseRepository(session).get_by_public_id(UUID(body.course_public_id))
            if course:
                CourseStudentRepository(session).enroll(course.id, user.id)
        except Exception:
            pass
    elif body.grade_public_id:
        try:
            grade = GradeRepository(session).get_by_public_id(UUID(body.grade_public_id))
            if grade:
                courses = CourseRepository(session).list_by_grade(grade.id)
                if courses:
                    CourseStudentRepository(session).enroll(courses[0].id, user.id)
        except Exception:
            pass

    return {"ok": True, "action": "upsert", "created": created, "matched": 1}
