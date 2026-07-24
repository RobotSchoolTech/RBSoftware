from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.types import Uuid
from sqlmodel import Field, SQLModel


class LmsCourse(SQLModel, table=True):
    __tablename__ = "lms_courses"

    id: int | None = Field(default=None, primary_key=True)
    public_id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(Uuid(as_uuid=True, native_uuid=False), nullable=False, unique=True),
    )
    grade_id: int = Field(
        sa_column=Column(
            Integer, ForeignKey("lms_grades.id", ondelete="CASCADE"), nullable=False
        )
    )
    school_id: int = Field(
        sa_column=Column(
            Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False
        )
    )
    name: str = Field(sa_column=Column(String(255), nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    teacher_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True
        )
    )
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )
