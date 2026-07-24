from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict
from sqlmodel import SQLModel


class CourseCreate(SQLModel):
    name: str
    description: str | None = None
    is_active: bool = True


class CourseRead(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: UUID
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MyCourseRead(SQLModel):
    """Enriched course info for the /my-courses endpoint."""

    public_id: UUID
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    grade_name: str
    school_name: str
    teacher_names: list[str] = []
    role: Literal['TEACHER', 'STUDENT']


class CourseUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
