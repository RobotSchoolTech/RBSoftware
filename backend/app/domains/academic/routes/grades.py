from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session

from app.core.database import get_session
from app.domains.academic.repositories import GradeRepository
from app.domains.academic.schemas import (
    CourseCreate, CourseRead, GradeRead, GradeUpdate, GradeWithCourses,
)
from app.domains.academic.services import AcademicService
from app.core.permissions import require_roles
from app.domains.auth.dependencies import get_current_user
from app.domains.auth.models import User
from app.domains.auth.repositories import UserRepository

router = APIRouter(prefix="/academic", tags=["academic – grades"])
_svc = AcademicService()


class DirectorBody(BaseModel):
    user_id: UUID


class CourseCreateBody(CourseCreate):
    teacher_id: UUID


@router.get("/my-grades", response_model=list[GradeRead])
def my_grades(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("DIRECTOR")),
):
    return [
        GradeRead.model_validate(g)
        for g in _svc.get_my_grades_as_director(session, current_user.id)
    ]


@router.get("/grades/{grade_id}", response_model=GradeWithCourses)
def get_grade(
    grade_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "DIRECTOR")),
):
    grade = GradeRepository(session).get_by_public_id(grade_id)
    if grade is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grade not found")
    try:
        return _svc.get_grade_detail(session, grade.id, current_user.id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))


@router.patch("/grades/{grade_id}", response_model=GradeRead)
def update_grade(
    grade_id: UUID,
    data: GradeUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "DIRECTOR")),
):
    grade = GradeRepository(session).get_by_public_id(grade_id)
    if grade is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grade not found")
    try:
        updated = _svc.update_grade(session, grade.id, data, current_user.id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    return GradeRead.model_validate(updated)


@router.delete("/grades/{grade_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_grade(
    grade_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN")),
):
    grade = GradeRepository(session).get_by_public_id(grade_id)
    if grade is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grade not found")
    try:
        _svc.delete_grade(session, grade.id, current_user.id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.post("/grades/{grade_id}/director", status_code=status.HTTP_204_NO_CONTENT)
def assign_director(
    grade_id: UUID,
    body: DirectorBody,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN")),
):
    grade = GradeRepository(session).get_by_public_id(grade_id)
    if grade is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grade not found")
    user = UserRepository(session).get_by_public_id(body.user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    try:
        _svc.assign_director(session, grade.id, user.id, current_user.id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.delete("/grades/{grade_id}/director", status_code=status.HTTP_204_NO_CONTENT)
def unassign_director(
    grade_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN")),
):
    grade = GradeRepository(session).get_by_public_id(grade_id)
    if grade is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grade not found")
    try:
        _svc.unassign_director(session, grade.id, current_user.id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.get("/grades/{grade_id}/courses", response_model=list[CourseRead])
def list_courses(
    grade_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "DIRECTOR")),
):
    grade = GradeRepository(session).get_by_public_id(grade_id)
    if grade is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grade not found")
    try:
        courses = _svc.list_grade_courses(session, grade.id, current_user.id)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    return [CourseRead.model_validate(c) for c in courses]


@router.post(
    "/grades/{grade_id}/courses",
    response_model=CourseRead,
    status_code=status.HTTP_201_CREATED,
)
def create_course(
    grade_id: UUID,
    body: CourseCreateBody,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "DIRECTOR")),
):
    grade = GradeRepository(session).get_by_public_id(grade_id)
    if grade is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grade not found")
    teacher = UserRepository(session).get_by_public_id(body.teacher_id)
    if teacher is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Teacher not found")
    data = CourseCreate(
        name=body.name,
        description=body.description,
        is_active=body.is_active,
    )
    try:
        course = _svc.create_course(
            session, grade.id, data, teacher.id, current_user.id
        )
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return CourseRead.model_validate(course)
