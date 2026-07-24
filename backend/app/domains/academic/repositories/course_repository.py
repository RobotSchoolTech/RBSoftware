from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from app.domains.academic.models.lms_course import LmsCourse
from app.domains.academic.models.lms_course_student import LmsCourseStudent
from app.domains.academic.models.lms_course_teacher import LmsCourseTeacher
from app.domains.academic.schemas.lms_course import CourseCreate, CourseUpdate
from app.domains.auth.models import User


class CourseRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        grade_id: int,
        school_id: int,
        teacher_id: int | None,
        payload: CourseCreate,
    ) -> LmsCourse:
        course = LmsCourse.model_validate(
            payload,
            update={
                "grade_id": grade_id,
                "school_id": school_id,
                "teacher_id": teacher_id,
            },
        )
        self.session.add(course)
        self.session.commit()
        self.session.refresh(course)
        return course

    def get_by_id(self, course_id: int) -> LmsCourse | None:
        return self.session.get(LmsCourse, course_id)

    def get_by_public_id(self, public_id: UUID) -> LmsCourse | None:
        stmt = select(LmsCourse).where(LmsCourse.public_id == public_id)
        return self.session.exec(stmt).first()

    def list_by_grade(self, grade_id: int) -> list[LmsCourse]:
        stmt = (
            select(LmsCourse)
            .where(LmsCourse.grade_id == grade_id)
            .order_by(LmsCourse.name)
        )
        return list(self.session.exec(stmt).all())

    def list_by_teacher(self, teacher_id: int) -> list[LmsCourse]:
        stmt = (
            select(LmsCourse)
            .join(LmsCourseTeacher, LmsCourseTeacher.course_id == LmsCourse.id)
            .where(
                LmsCourseTeacher.user_id == teacher_id,
                LmsCourse.is_active.is_(True),
            )
            .order_by(LmsCourse.name)
        )
        return list(self.session.exec(stmt).all())

    def list_all_active(self) -> list[LmsCourse]:
        stmt = (
            select(LmsCourse)
            .where(LmsCourse.is_active.is_(True))
            .order_by(LmsCourse.name)
        )
        return list(self.session.exec(stmt).all())

    def list_by_grade_ids(self, grade_ids: list[int]) -> list[LmsCourse]:
        if not grade_ids:
            return []
        stmt = (
            select(LmsCourse)
            .where(
                LmsCourse.grade_id.in_(grade_ids),
                LmsCourse.is_active.is_(True),
            )
            .order_by(LmsCourse.name)
        )
        return list(self.session.exec(stmt).all())

    def list_by_school(self, school_id: int) -> list[LmsCourse]:
        stmt = (
            select(LmsCourse)
            .where(LmsCourse.school_id == school_id)
            .order_by(LmsCourse.name)
        )
        return list(self.session.exec(stmt).all())

    def get_with_students(self, course_id: int) -> tuple[LmsCourse, list[User]] | None:
        course = self.get_by_id(course_id)
        if course is None:
            return None
        stmt = (
            select(User)
            .join(LmsCourseStudent, LmsCourseStudent.user_id == User.id)
            .where(
                LmsCourseStudent.course_id == course_id,
                LmsCourseStudent.is_active.is_(True),
            )
            .order_by(User.last_name, User.first_name)
        )
        students = list(self.session.exec(stmt).all())
        return course, students

    def update(self, course: LmsCourse, payload: CourseUpdate) -> LmsCourse:
        updates = payload.model_dump(exclude_unset=True)
        for field_name, value in updates.items():
            setattr(course, field_name, value)
        self.session.add(course)
        self.session.commit()
        self.session.refresh(course)
        return course

    def delete(self, course: LmsCourse) -> None:
        self.session.delete(course)
        self.session.commit()
