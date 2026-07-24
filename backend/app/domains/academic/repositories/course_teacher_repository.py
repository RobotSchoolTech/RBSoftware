from __future__ import annotations

from sqlmodel import Session, select

from app.domains.academic.models.lms_course_teacher import LmsCourseTeacher
from app.domains.auth.models import User


class CourseTeacherRepository:
    """Tabla puente curso<->docente (co-dictado). Clon de SchoolTeacherRepository."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, course_id: int, user_id: int) -> LmsCourseTeacher:
        existing = self._get_record(course_id, user_id)
        if existing is not None:
            return existing
        record = LmsCourseTeacher(course_id=course_id, user_id=user_id)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def remove(self, course_id: int, user_id: int) -> bool:
        record = self._get_record(course_id, user_id)
        if record is None:
            return False
        self.session.delete(record)
        self.session.commit()
        return True

    def get_teacher_ids(self, course_id: int) -> list[int]:
        stmt = select(LmsCourseTeacher.user_id).where(
            LmsCourseTeacher.course_id == course_id
        )
        return list(self.session.exec(stmt).all())

    def is_course_teacher(self, course_id: int, user_id: int) -> bool:
        return self._get_record(course_id, user_id) is not None

    def list_teachers(self, course_id: int) -> list[User]:
        stmt = (
            select(User)
            .join(LmsCourseTeacher, LmsCourseTeacher.user_id == User.id)
            .where(LmsCourseTeacher.course_id == course_id)
            .order_by(User.first_name, User.last_name)
        )
        return list(self.session.exec(stmt).all())

    def list_course_ids_for_teacher(self, user_id: int) -> list[int]:
        stmt = select(LmsCourseTeacher.course_id).where(
            LmsCourseTeacher.user_id == user_id
        )
        return list(self.session.exec(stmt).all())

    def _get_record(self, course_id: int, user_id: int) -> LmsCourseTeacher | None:
        stmt = select(LmsCourseTeacher).where(
            LmsCourseTeacher.course_id == course_id,
            LmsCourseTeacher.user_id == user_id,
        )
        return self.session.exec(stmt).first()
