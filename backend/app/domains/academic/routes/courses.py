from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlmodel import Session

from app.core.database import get_session
from app.domains.academic.repositories import (
    AssignmentRepository,
    CourseRepository,
    RubricRepository,
)
from app.domains.academic.schemas import (
    AssignmentRead, CourseDetail, CourseRead, CourseUpdate,
    MaterialRead, MyCourseRead, SubmissionRead, UnitRead,
)
from app.domains.academic.services import AcademicService
from app.core.permissions import require_roles
from app.domains.auth.dependencies import get_current_user
from app.domains.auth.models import User
from app.domains.auth.repositories import UserRepository
from app.domains.auth.schemas.user import UserRead

router = APIRouter(prefix="/academic", tags=["academic – courses"])
_svc = AcademicService()


class TeacherBody(BaseModel):
    teacher_id: UUID


class EnrollBody(BaseModel):
    user_id: UUID


class _AssignmentStudentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: UUID
    title: str
    description: str | None
    due_date: datetime | None
    max_score: int
    is_published: bool
    my_submission: SubmissionRead | None = None


class _UnitStudentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: UUID
    title: str
    description: str | None
    order_index: int
    is_published: bool
    materials: list[MaterialRead] = []
    assignments: list[_AssignmentStudentView] = []


@router.get("/my-courses", response_model=list[MyCourseRead])
def my_courses(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return _svc.get_my_courses(session, current_user.id)


@router.get("/courses/{course_id}", response_model=CourseDetail)
def get_course(
    course_id: UUID,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    course = CourseRepository(session).get_by_public_id(course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    try:
        return _svc.get_course_detail(session, course.id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.patch("/courses/{course_id}", response_model=CourseRead)
def update_course(
    course_id: UUID,
    data: CourseUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "DIRECTOR")),
):
    course = CourseRepository(session).get_by_public_id(course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    try:
        updated = _svc.update_course(session, course.id, data, current_user.id)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    return CourseRead.model_validate(updated)


@router.get(
    "/courses/{course_id}/assignable-teachers", response_model=list[UserRead]
)
def list_assignable_teachers(
    course_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "DIRECTOR")),
):
    course = CourseRepository(session).get_by_public_id(course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    try:
        return _svc.get_assignable_teachers_for_course(
            session, course.id, current_user.id
        )
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))


@router.post("/courses/{course_id}/teachers", status_code=status.HTTP_204_NO_CONTENT)
def add_course_teacher(
    course_id: UUID,
    body: TeacherBody,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN")),
):
    course = CourseRepository(session).get_by_public_id(course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    teacher = UserRepository(session).get_by_public_id(body.teacher_id)
    if teacher is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Teacher not found")
    try:
        _svc.add_teacher_to_course(session, course.id, teacher.id, current_user.id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.delete(
    "/courses/{course_id}/teachers/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_course_teacher(
    course_id: UUID,
    user_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN")),
):
    course = CourseRepository(session).get_by_public_id(course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    teacher = UserRepository(session).get_by_public_id(user_id)
    if teacher is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Teacher not found")
    try:
        _svc.remove_teacher_from_course(session, course.id, teacher.id, current_user.id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/courses/{course_id}/students", response_model=list[UserRead])
def list_students(
    course_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "DIRECTOR", "TEACHER")),
):
    course = CourseRepository(session).get_by_public_id(course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    try:
        students = _svc.list_course_students(session, course.id, current_user.id)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    return [UserRead.model_validate(s) for s in students]


@router.post(
    "/courses/{course_id}/students",
    status_code=status.HTTP_204_NO_CONTENT,
)
def enroll_student(
    course_id: UUID,
    body: EnrollBody,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "DIRECTOR")),
):
    course = CourseRepository(session).get_by_public_id(course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    user = UserRepository(session).get_by_public_id(body.user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    try:
        _svc.enroll_student(session, course.id, user.id, current_user.id)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.delete(
    "/courses/{course_id}/students/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unenroll_student(
    course_id: UUID,
    user_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "DIRECTOR")),
):
    course = CourseRepository(session).get_by_public_id(course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    user = UserRepository(session).get_by_public_id(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    try:
        _svc.unenroll_student(session, course.id, user.id, current_user.id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))


@router.get("/courses/{course_id}/content", response_model=list[_UnitStudentView])
def get_course_content(
    course_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    course = CourseRepository(session).get_by_public_id(course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    try:
        _, units_data = _svc.get_course_content(
            session, course.id, current_user.id
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    result = []
    for unit, materials, assignment_pairs in units_data:
        result.append(
            _UnitStudentView(
                public_id=unit.public_id,
                title=unit.title,
                description=unit.description,
                order_index=unit.order_index,
                is_published=unit.is_published,
                materials=[MaterialRead.model_validate(m) for m in materials],
                assignments=[
                    _AssignmentStudentView(
                        public_id=a.public_id,
                        title=a.title,
                        description=a.description,
                        due_date=a.due_date,
                        max_score=a.max_score,
                        is_published=a.is_published,
                        my_submission=(
                            SubmissionRead.model_validate(sub) if sub else None
                        ),
                    )
                    for a, sub in assignment_pairs
                ],
            )
        )
    return result


@router.get("/courses/{course_id}/gradebook")
def get_gradebook(
    course_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "TEACHER", "DIRECTOR")),
):
    course = CourseRepository(session).get_by_public_id(course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    try:
        return _svc.get_gradebook(session, course.id, current_user.id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))


class _RubricLevelBody(BaseModel):
    title: str
    description: str | None = None
    points: int


class _RubricCriteriaBody(BaseModel):
    title: str
    description: str | None = None
    weight: int = 1
    levels: list[_RubricLevelBody] = []


class RubricBody(BaseModel):
    title: str
    description: str | None = None
    criteria: list[_RubricCriteriaBody] = []


@router.get("/assignments/{assignment_id}/rubric")
def get_assignment_rubric(
    assignment_id: UUID,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    assignment = AssignmentRepository(session).get_by_public_id(assignment_id)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")
    repo = RubricRepository(session)
    rubric = repo.get_by_assignment(assignment.id)
    if rubric is None:
        return None
    return repo.get_full(rubric.id)


@router.put("/assignments/{assignment_id}/rubric")
def upsert_assignment_rubric(
    assignment_id: UUID,
    body: RubricBody,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN", "TEACHER")),
):
    assignment = AssignmentRepository(session).get_by_public_id(assignment_id)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")
    repo = RubricRepository(session)
    rubric = repo.upsert_full(body.model_dump(), assignment_id=assignment.id)
    return repo.get_full(rubric.id)
