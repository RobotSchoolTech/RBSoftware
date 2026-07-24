from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlmodel import Field, SQLModel


class LmsCourseTeacher(SQLModel, table=True):
    """Tabla puente curso<->docente (co-dictado). Clon de SchoolTeacher.

    A diferencia de SchoolTeacher, user_id usa ondelete="RESTRICT": borrar un
    usuario no debe hacer desaparecer en silencio el historial de quien dicto
    un curso; debe fallar y forzar una decision explicita.
    """

    __tablename__ = "lms_course_teachers"
    __table_args__ = (
        UniqueConstraint("course_id", "user_id", name="uq_lms_course_teachers_course_user"),
    )

    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(
        sa_column=Column(
            Integer, ForeignKey("lms_courses.id", ondelete="CASCADE"), nullable=False
        )
    )
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
