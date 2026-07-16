from __future__ import annotations

from sqlmodel import Session, select

from app.domains.academic.models.lms_grade import LmsGrade
from app.domains.academic.models.lms_grade_director import LmsGradeDirector
from app.domains.auth.models import User


class GradeDirectorRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def assign(self, grade_id: int, user_id: int) -> LmsGradeDirector:
        existing = self._get_record(grade_id, user_id)
        if existing is not None:
            if not existing.is_active:
                existing.is_active = True
                self.session.add(existing)
                self.session.commit()
                self.session.refresh(existing)
            return existing
        record = LmsGradeDirector(grade_id=grade_id, user_id=user_id, is_active=True)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def unassign(self, grade_id: int, user_id: int) -> bool:
        record = self._get_record(grade_id, user_id)
        if record is None or not record.is_active:
            return False
        record.is_active = False
        self.session.add(record)
        self.session.commit()
        return True

    def get_active_director(self, grade_id: int) -> User | None:
        stmt = (
            select(User)
            .join(LmsGradeDirector, LmsGradeDirector.user_id == User.id)
            .where(
                LmsGradeDirector.grade_id == grade_id,
                LmsGradeDirector.is_active.is_(True),
            )
        )
        return self.session.exec(stmt).first()

    def get_grades_for_director(self, user_id: int) -> list[LmsGrade]:
        stmt = (
            select(LmsGrade)
            .join(LmsGradeDirector, LmsGradeDirector.grade_id == LmsGrade.id)
            .where(
                LmsGradeDirector.user_id == user_id,
                LmsGradeDirector.is_active.is_(True),
            )
            .order_by(LmsGrade.name)
        )
        return list(self.session.exec(stmt).all())

    def list_directors_in_school(self, school_id: int) -> list[User]:
        stmt = (
            select(User)
            .join(LmsGradeDirector, LmsGradeDirector.user_id == User.id)
            .join(LmsGrade, LmsGrade.id == LmsGradeDirector.grade_id)
            .where(
                LmsGrade.school_id == school_id,
                LmsGradeDirector.is_active.is_(True),
            )
            .distinct()
        )
        return list(self.session.exec(stmt).all())

    def is_director_of_grade(self, grade_id: int, user_id: int) -> bool:
        record = self._get_record(grade_id, user_id)
        return record is not None and record.is_active

    def is_director_in_school(self, school_id: int, user_id: int) -> bool:
        stmt = (
            select(LmsGradeDirector)
            .join(LmsGrade, LmsGrade.id == LmsGradeDirector.grade_id)
            .where(
                LmsGrade.school_id == school_id,
                LmsGradeDirector.user_id == user_id,
                LmsGradeDirector.is_active.is_(True),
            )
        )
        return self.session.exec(stmt).first() is not None

    def _get_record(self, grade_id: int, user_id: int) -> LmsGradeDirector | None:
        stmt = select(LmsGradeDirector).where(
            LmsGradeDirector.grade_id == grade_id,
            LmsGradeDirector.user_id == user_id,
        )
        return self.session.exec(stmt).first()
