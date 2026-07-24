from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict
from sqlmodel import SQLModel

from app.domains.academic.schemas.lms_assignment import AssignmentRead
from app.domains.academic.schemas.lms_course import CourseRead
from app.domains.academic.schemas.lms_material import MaterialRead
from app.domains.academic.schemas.lms_submission import SubmissionRead
from app.domains.academic.schemas.lms_unit import UnitRead
from app.domains.auth.schemas.user import UserRead


class GradeWithCourses(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: UUID
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    school_public_id: UUID | None = None
    courses: list[CourseRead] = []
    director: UserRead | None = None


class CourseDetail(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: UUID
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    teachers: list[UserRead] = []
    students: list[UserRead] = []
    units: list[UnitRead] = []


class UnitWithContent(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: UUID
    title: str
    description: str | None
    order_index: int
    is_published: bool
    materials: list[MaterialRead] = []
    assignments: list[AssignmentRead] = []


class SubmissionWithStudent(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: UUID
    content: str | None
    file_name: str | None
    status: Literal['PENDING', 'SUBMITTED', 'GRADED']
    score: int | None
    feedback: str | None
    submitted_at: datetime | None
    graded_at: datetime | None
    created_at: datetime
    updated_at: datetime
    student: UserRead


class AssignmentWithSubmissions(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: UUID
    title: str
    description: str | None
    due_date: datetime | None
    max_score: int
    is_published: bool
    submissions: list[SubmissionWithStudent] = []


class StudentCourseProgress(SQLModel):
    course_id: UUID
    total_assignments: int
    submitted: int
    graded: int
    average_score: float | None
