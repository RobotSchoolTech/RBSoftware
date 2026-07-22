from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlmodel import Session, select

from app.core.storage import storage_service
from app.domains.academic.models.lms_assignment import LmsAssignment
from app.domains.academic.models.lms_course import LmsCourse
from app.domains.academic.models.lms_grade import LmsGrade
from app.domains.academic.models.lms_material import LmsMaterial
from app.domains.academic.models.lms_submission import LmsSubmission, SubmissionStatus
from app.domains.academic.models.lms_unit import LmsUnit
from app.domains.academic.models.school import School
from app.domains.academic.repositories import (
    AssignmentRepository,
    CourseRepository,
    CourseStudentRepository,
    GradeDirectorRepository,
    GradeRepository,
    MaterialRepository,
    PDFAnnotationRepository,
    SchoolRepository,
    SchoolTeacherRepository,
    SubmissionRepository,
    UnitRepository,
)
from app.domains.academic.schemas.composite import CourseDetail, GradeWithCourses
from app.domains.academic.schemas.lms_assignment import (
    AssignmentCreate,
    AssignmentUpdate,
)
from app.domains.academic.schemas.lms_course import CourseCreate, CourseRead, CourseUpdate, MyCourseRead
from app.domains.academic.schemas.lms_grade import GradeCreate, GradeUpdate
from app.domains.academic.schemas.lms_material import MaterialCreate
from app.domains.academic.schemas.lms_submission import SubmissionUpdate
from app.domains.academic.schemas.lms_unit import UnitCreate, UnitRead, UnitUpdate
from app.domains.academic.schemas.school import SchoolCreate
from app.domains.audit.services import AuditService
from app.domains.auth.models import User
from app.domains.auth.repositories import UserRepository
from app.domains.auth.schemas.user import UserRead
from app.domains.rbac.repositories import UserRoleRepository
from app.domains.repository.models.repository_file import RepositoryFile
from app.domains.repository.services.visibility import can_see_file, get_user_scopes

_audit = AuditService()


# Colombia y Ecuador (las líneas de trabajo del LMS) son UTC-5 fijo, sin horario
# de verano. Se usa un offset constante en vez de zoneinfo para no depender de
# tzdata en Windows/dev. Revisar si el LMS se expande a otra zona horaria.
_LOCAL_UTC_OFFSET = timedelta(hours=5)


def is_submission_late(
    submitted_at: datetime | None, due_date: datetime | None
) -> bool:
    """¿La entrega fue posterior al límite?

    Marcador suave (no bloquea la entrega). Solo aplica si la actividad tiene
    fecha límite y la entrega ya ocurrió.

    Las dos marcas viven en referencias distintas en la BD: ``submitted_at`` se
    guarda en UTC (``datetime.now(timezone.utc)`` server-side) y ``due_date`` en
    hora local (el calendario la manda como wall-clock local, igual que el viejo
    ``datetime-local``). MySQL devuelve ambas naive en columnas
    ``DateTime(timezone=True)``, así que hay que llevar ``submitted_at`` a hora
    local antes de comparar; compararlas crudas daría un sesgo de 5 h.
    """
    if submitted_at is None or due_date is None:
        return False
    submitted_local = submitted_at.replace(tzinfo=None) - _LOCAL_UTC_OFFSET
    due = due_date.replace(tzinfo=None)
    return submitted_local > due


class AcademicService:

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _is_admin(session: Session, user_id: int) -> bool:
        role_names = UserRoleRepository(session).get_role_names_for_user(user_id)
        return "ADMIN" in role_names

    @staticmethod
    def _detect_content_type(file_name: str | None) -> str:
        if not file_name:
            return "application/octet-stream"
        ext = file_name.rsplit(".", 1)[-1].lower()
        return {
            "pdf": "application/pdf",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "webp": "image/webp",
        }.get(ext, "application/octet-stream")

    def _assert_admin_or_director(
        self, session: Session, grade_id: int, user_id: int
    ) -> None:
        if self._is_admin(session, user_id):
            return
        if GradeDirectorRepository(session).is_director_of_grade(grade_id, user_id):
            return
        raise PermissionError("User must be admin or director of this grade")

    def _assert_admin_or_director_or_teacher(
        self, session: Session, course: LmsCourse, user_id: int
    ) -> None:
        if self._is_admin(session, user_id):
            return
        if GradeDirectorRepository(session).is_director_of_grade(
            course.grade_id, user_id
        ):
            return
        if course.teacher_id == user_id:
            return
        raise PermissionError(
            "User must be admin, director of this grade, or teacher of this course"
        )

    def _assert_admin_or_teacher(
        self, session: Session, course: LmsCourse, user_id: int
    ) -> None:
        if self._is_admin(session, user_id):
            return
        if course.teacher_id == user_id:
            return
        raise PermissionError("User must be admin or teacher of this course")

    # ── Schools ──────────────────────────────────────────────────────────────

    def create_school(self, session: Session, data: SchoolCreate) -> School:
        return SchoolRepository(session).create(data)

    def add_member_to_school(
        self,
        session: Session,
        school_id: int,
        user_id: int,
        requesting_user_id: int,
    ) -> None:
        if not self._is_admin(session, requesting_user_id):
            raise PermissionError("Solo administradores pueden asignar miembros")

        school = SchoolRepository(session).get_by_id(school_id)
        if school is None:
            raise LookupError("Colegio no encontrado")

        user = UserRepository(session).get_by_id(user_id)
        if user is None:
            raise LookupError("Usuario no encontrado")

        role_names = UserRoleRepository(session).get_role_names_for_user(user.id)
        if "TEACHER" not in role_names and "STUDENT" not in role_names:
            raise ValueError("El usuario debe tener rol TEACHER o STUDENT")

        SchoolTeacherRepository(session).add(school_id, user_id)

        _audit.log(
            session,
            user_id=requesting_user_id,
            action="academic.school.member_added",
            resource_type="school",
            resource_id=str(school.id),
            payload={"member_user_id": user_id},
        )

    def remove_teacher_from_school(
        self,
        session: Session,
        school_id: int,
        user_id: int,
        requesting_user_id: int,
    ) -> None:
        if not self._is_admin(session, requesting_user_id):
            raise PermissionError("Solo administradores pueden remover docentes")

        active_courses = [
            c for c in CourseRepository(session).list_by_school(school_id)
            if c.teacher_id == user_id and c.is_active
        ]
        if active_courses:
            raise ValueError("El docente tiene cursos activos en este colegio")

        SchoolTeacherRepository(session).remove(school_id, user_id)

        _audit.log(
            session,
            user_id=requesting_user_id,
            action="academic.school.teacher_removed",
            resource_type="school",
            resource_id=str(school_id),
            payload={"teacher_user_id": user_id},
        )

    def get_teachers_for_school(
        self,
        session: Session,
        school_id: int,
        requesting_user_id: int,
    ) -> list[UserRead]:
        if not self._is_admin(session, requesting_user_id):
            roles = UserRoleRepository(session).get_role_names_for_user(requesting_user_id)
            if "TRAINER" not in roles and "SUPER_TRAINER" not in roles:
                grades = GradeDirectorRepository(session).get_grades_for_director(
                    requesting_user_id
                )
                school_ids = {g.school_id for g in grades}
                if school_id not in school_ids:
                    raise PermissionError(
                        "Solo administradores, directores del colegio o trainers pueden ver docentes"
                    )

        members = SchoolTeacherRepository(session).list_teachers(school_id)
        role_repo = UserRoleRepository(session)
        result = []
        for user in members:
            role_names = role_repo.get_role_names_for_user(user.id)
            if "TEACHER" in role_names:
                result.append(
                    UserRead.model_validate(user).model_copy(update={"roles": role_names})
                )
        return result

    def get_students_for_school(
        self,
        session: Session,
        school_id: int,
        requesting_user_id: int,
    ) -> list[UserRead]:
        if not self._is_admin(session, requesting_user_id):
            grades = GradeDirectorRepository(session).get_grades_for_director(
                requesting_user_id
            )
            school_ids = {g.school_id for g in grades}
            if school_id not in school_ids:
                raise PermissionError(
                    "Solo administradores o directores del colegio pueden ver estudiantes"
                )

        members = SchoolTeacherRepository(session).list_teachers(school_id)
        role_repo = UserRoleRepository(session)
        result = []
        for user in members:
            role_names = role_repo.get_role_names_for_user(user.id)
            if "STUDENT" in role_names:
                result.append(
                    UserRead.model_validate(user).model_copy(update={"roles": role_names})
                )
        return result

    def get_user_school_affiliation(
        self, session: Session, user_public_id: UUID
    ) -> dict:
        user = UserRepository(session).get_by_public_id(user_public_id)
        if user is None:
            raise LookupError("Usuario no encontrado")

        role_names = UserRoleRepository(session).get_role_names_for_user(user.id)

        if "TEACHER" in role_names:
            schools = SchoolTeacherRepository(session).get_schools_for_teacher(user.id)
            if schools:
                s = schools[0]
                return {
                    "role": "TEACHER",
                    "school": {"public_id": str(s.public_id), "name": s.name},
                    "grade": None,
                    "course": None,
                }

        if "DIRECTOR" in role_names:
            grades = GradeDirectorRepository(session).get_grades_for_director(user.id)
            if grades:
                g = grades[0]
                s = SchoolRepository(session).get_by_id(g.school_id)
                return {
                    "role": "DIRECTOR",
                    "school": {"public_id": str(s.public_id), "name": s.name},
                    "grade": {"public_id": str(g.public_id), "name": g.name},
                    "course": None,
                }

        if "STUDENT" in role_names:
            schools = SchoolTeacherRepository(session).get_schools_for_teacher(user.id)
            if schools:
                s = schools[0]
                return {
                    "role": "STUDENT",
                    "school": {"public_id": str(s.public_id), "name": s.name},
                    "grade": None,
                    "course": None,
                }

        return {"role": None, "school": None, "grade": None, "course": None}

    # ── Grades ───────────────────────────────────────────────────────────────

    def create_grade(
        self, session: Session, school_id: int, data: GradeCreate
    ) -> LmsGrade:
        school = SchoolRepository(session).get_by_id(school_id)
        if school is None:
            raise LookupError("School not found")
        return GradeRepository(session).create(school.id, data)

    def assign_director(
        self,
        session: Session,
        grade_id: int,
        user_id: int,
        requesting_user_id: int,
    ) -> None:
        grade = GradeRepository(session).get_by_id(grade_id)
        if grade is None:
            raise LookupError("Grade not found")

        user = UserRepository(session).get_by_id(user_id)
        if user is None:
            raise LookupError("User not found")

        director_repo = GradeDirectorRepository(session)

        # Un director puede dirigir varios grados, incluso dentro de la misma
        # escuela: el modelo lo permite (UniqueConstraint sobre el par
        # grade_id+user_id, no sobre el director) y get_grades_for_director
        # devuelve una lista. La única invariante es un director *activo* por
        # grado, que se garantiza abajo desasignando al anterior.

        current = director_repo.get_active_director(grade_id)
        if current is not None:
            director_repo.unassign(grade_id, current.id)

        director_repo.assign(grade_id, user_id)

        _audit.log(
            session,
            user_id=requesting_user_id,
            action="academic.grade.director_assigned",
            resource_type="lms_grade",
            resource_id=str(grade.id),
            payload={"director_user_id": user_id},
        )

    def unassign_director(
        self, session: Session, grade_id: int, requesting_user_id: int
    ) -> None:
        grade = GradeRepository(session).get_by_id(grade_id)
        if grade is None:
            raise LookupError("Grade not found")
        director_repo = GradeDirectorRepository(session)
        director = director_repo.get_active_director(grade.id)
        if director is None:
            raise LookupError("No active director")
        director_repo.unassign(grade.id, director.id)
        _audit.log(
            session,
            user_id=requesting_user_id,
            action="academic.grade.director_unassigned",
            resource_type="lms_grade",
            resource_id=str(grade.id),
        )

    def get_grade_detail(
        self, session: Session, grade_id: int, user_id: int
    ) -> GradeWithCourses:
        grade = GradeRepository(session).get_by_id(grade_id)
        if grade is None:
            raise LookupError("Grade not found")
        self._assert_admin_or_director(session, grade.id, user_id)
        result = GradeRepository(session).get_with_courses(grade.id)
        if result is None:
            raise LookupError("Grade not found")
        grade_obj, courses, director = result
        school = SchoolRepository(session).get_by_id(grade_obj.school_id)
        return GradeWithCourses(
            public_id=grade_obj.public_id,
            name=grade_obj.name,
            description=grade_obj.description,
            is_active=grade_obj.is_active,
            created_at=grade_obj.created_at,
            updated_at=grade_obj.updated_at,
            school_public_id=school.public_id if school else None,
            director=UserRead.model_validate(director) if director else None,
            courses=[CourseRead.model_validate(c) for c in courses],
        )

    def update_grade(
        self, session: Session, grade_id: int, data: GradeUpdate, user_id: int
    ) -> LmsGrade:
        grade = GradeRepository(session).get_by_id(grade_id)
        if grade is None:
            raise LookupError("Grade not found")
        self._assert_admin_or_director(session, grade.id, user_id)
        return GradeRepository(session).update(grade, data)

    def delete_grade(
        self, session: Session, grade_id: int, user_id: int
    ) -> None:
        grade = GradeRepository(session).get_by_id(grade_id)
        if grade is None:
            raise LookupError("Grade not found")
        # Guarda anti-cascada: el FK lms_courses.grade_id es ON DELETE CASCADE,
        # así que borrar un grado con cursos arrastraría cursos, estudiantes,
        # entregas, etc. Solo se permite borrar grados vacíos.
        courses = session.exec(
            select(LmsCourse).where(LmsCourse.grade_id == grade.id)
        ).all()
        if courses:
            raise ValueError(
                "No se puede eliminar un grado que tiene cursos. "
                "Elimina o reasigna sus cursos primero."
            )
        GradeRepository(session).delete(grade)
        _audit.log(
            session,
            user_id=user_id,
            action="academic.grade.deleted",
            resource_type="lms_grade",
            resource_id=str(grade.id),
            payload={"name": grade.name, "school_id": grade.school_id},
        )

    def list_grade_courses(
        self, session: Session, grade_id: int, user_id: int
    ) -> list[LmsCourse]:
        grade = GradeRepository(session).get_by_id(grade_id)
        if grade is None:
            raise LookupError("Grade not found")
        self._assert_admin_or_director(session, grade.id, user_id)
        return CourseRepository(session).list_by_grade(grade.id)

    # ── Courses ──────────────────────────────────────────────────────────────

    def get_my_courses(
        self, session: Session, user_id: int
    ) -> list[MyCourseRead]:
        teacher_courses = self.get_my_courses_as_teacher(session, user_id)
        student_courses = self.get_my_courses_as_student(session, user_id)

        teacher_ids = {c.id for c in teacher_courses}
        all_courses = []
        seen: set[int] = set()
        for c in teacher_courses + student_courses:
            if c.id not in seen:
                seen.add(c.id)
                all_courses.append(c)

        if not all_courses:
            return []

        grade_ids = {c.grade_id for c in all_courses}
        school_ids = {c.school_id for c in all_courses}
        t_ids = {c.teacher_id for c in all_courses}

        grade_repo = GradeRepository(session)
        school_repo = SchoolRepository(session)
        user_repo = UserRepository(session)

        grades_map = {g.id: g for g in [grade_repo.get_by_id(gid) for gid in grade_ids] if g}
        schools_map = {s.id: s for s in [school_repo.get_by_id(sid) for sid in school_ids] if s}
        teachers_map = {t.id: t for t in [user_repo.get_by_id(tid) for tid in t_ids] if t}

        result: list[MyCourseRead] = []
        for c in all_courses:
            grade = grades_map.get(c.grade_id)
            school = schools_map.get(c.school_id)
            teacher = teachers_map.get(c.teacher_id)
            result.append(
                MyCourseRead(
                    public_id=c.public_id,
                    name=c.name,
                    description=c.description,
                    is_active=c.is_active,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                    grade_name=grade.name if grade else "",
                    school_name=school.name if school else "",
                    teacher_name=(
                        f"{teacher.first_name} {teacher.last_name}" if teacher else ""
                    ),
                    role="TEACHER" if c.id in teacher_ids else "STUDENT",
                )
            )
        return result

    def get_course_detail(
        self, session: Session, course_id: int
    ) -> CourseDetail:
        course = CourseRepository(session).get_by_id(course_id)
        if course is None:
            raise LookupError("Course not found")
        teacher = UserRepository(session).get_by_id(course.teacher_id)
        students = CourseStudentRepository(session).get_students(course.id)
        units = UnitRepository(session).list_by_course(course.id)
        return CourseDetail(
            public_id=course.public_id,
            name=course.name,
            description=course.description,
            is_active=course.is_active,
            created_at=course.created_at,
            updated_at=course.updated_at,
            teacher=UserRead.model_validate(teacher),
            students=[UserRead.model_validate(s) for s in students],
            units=[UnitRead.model_validate(u) for u in units],
        )

    def create_course(
        self,
        session: Session,
        grade_id: int,
        data: CourseCreate,
        teacher_id: int,
        requesting_user_id: int,
    ) -> LmsCourse:
        self._assert_admin_or_director(session, grade_id, requesting_user_id)

        grade = GradeRepository(session).get_by_id(grade_id)
        if grade is None:
            raise LookupError("Grade not found")

        # Un director puede dictar cursos: en RobotSchool la misma persona
        # coordina un grado y tiene curso a cargo.
        course = CourseRepository(session).create(
            grade_id, grade.school_id, teacher_id, data
        )

        _audit.log(
            session,
            user_id=requesting_user_id,
            action="academic.course.created",
            resource_type="lms_course",
            resource_id=str(course.id),
        )
        return course

    def update_course(
        self, session: Session, course_id: int, data: CourseUpdate, user_id: int
    ) -> LmsCourse:
        course = CourseRepository(session).get_by_id(course_id)
        if course is None:
            raise LookupError("Course not found")
        self._assert_admin_or_director(session, course.grade_id, user_id)
        return CourseRepository(session).update(course, data)

    def get_course_deletion_impact(
        self,
        session: Session,
        course_id: int,
        requesting_user_id: int,
    ) -> dict:
        """Qué se destruiría al borrar el curso. Alimenta la confirmación de la UI.

        Borrar `lms_courses` arrastra en cascada (verificado contra las FKs de
        prod): lms_course_students · lms_units → lms_assignments → (
        lms_submissions + rubrics) · lms_units → lms_materials → pdf_annotations.
        """
        course = CourseRepository(session).get_by_id(course_id)
        if course is None:
            raise LookupError("Course not found")

        self._assert_admin_or_director(session, course.grade_id, requesting_user_id)

        units = session.exec(
            select(LmsUnit).where(LmsUnit.course_id == course.id)
        ).all()
        unit_ids = [u.id for u in units]

        # Todas las filas, no solo las activas: la cascada se lleva también las
        # matrículas dadas de baja (is_active=false), que son el histórico.
        students = len(
            session.exec(
                select(LmsCourseStudent).where(
                    LmsCourseStudent.course_id == course.id
                )
            ).all()
        )
        assignments = 0
        materials = 0
        submissions = 0
        if unit_ids:
            assignment_rows = session.exec(
                select(LmsAssignment).where(LmsAssignment.unit_id.in_(unit_ids))
            ).all()
            assignments = len(assignment_rows)
            materials = len(
                session.exec(
                    select(LmsMaterial).where(LmsMaterial.unit_id.in_(unit_ids))
                ).all()
            )
            if assignment_rows:
                submissions = len(
                    session.exec(
                        select(LmsSubmission).where(
                            LmsSubmission.assignment_id.in_(
                                [a.id for a in assignment_rows]
                            )
                        )
                    ).all()
                )

        return {
            "students": students,
            "units": len(units),
            "assignments": assignments,
            "materials": materials,
            "submissions": submissions,
            # El trabajo entregado por estudiantes no se puede reconstruir → si
            # existe, el borrado se bloquea (ver delete_course).
            "can_delete": submissions == 0,
        }

    def delete_course(
        self,
        session: Session,
        course_id: int,
        requesting_user_id: int,
    ) -> None:
        course = CourseRepository(session).get_by_id(course_id)
        if course is None:
            raise LookupError("Course not found")

        self._assert_admin_or_director(session, course.grade_id, requesting_user_id)

        impact = self.get_course_deletion_impact(session, course.id, requesting_user_id)
        # Guarda anti-cascada: matrículas y unidades se pueden rehacer; las
        # ENTREGAS de los estudiantes no. Si hay aunque sea una, no se borra.
        if impact["submissions"]:
            raise ValueError(
                f"No se puede eliminar un curso con entregas de estudiantes "
                f"({impact['submissions']}). El trabajo entregado no se puede "
                f"recuperar. Desactiva el curso en vez de eliminarlo."
            )

        # Capturar ANTES de borrar: tras el delete el objeto queda expirado y el
        # log se escribe después, para no dejar rastro de un borrado que falló.
        payload = {
            "name": course.name,
            "grade_id": course.grade_id,
            "school_id": course.school_id,
            "teacher_id": course.teacher_id,
            # Qué se llevó la cascada, para poder reconstruir el contexto.
            "cascaded": {
                k: impact[k]
                for k in ("students", "units", "assignments", "materials")
            },
        }
        course_id_val = course.id

        CourseRepository(session).delete(course)

        _audit.log(
            session,
            user_id=requesting_user_id,
            action="academic.course.deleted",
            resource_type="lms_course",
            resource_id=str(course_id_val),
            payload=payload,
        )

    def get_assignable_teachers_for_course(
        self,
        session: Session,
        course_id: int,
        requesting_user_id: int,
    ) -> list[UserRead]:
        """Candidatos a docente de un curso.

        Docentes del colegio + directores del colegio (la misma persona puede
        coordinar y dictar) + el docente actual, para que el select siempre
        muestre el valor vigente aunque su cuenta esté desactivada.
        """
        course = CourseRepository(session).get_by_id(course_id)
        if course is None:
            raise LookupError("Course not found")

        self._assert_admin_or_director(session, course.grade_id, requesting_user_id)

        role_repo = UserRoleRepository(session)
        candidates: dict[int, User] = {}

        for user in SchoolTeacherRepository(session).list_teachers(course.school_id):
            if not user.is_active:
                continue
            if "TEACHER" in role_repo.get_role_names_for_user(user.id):
                candidates[user.id] = user

        for user in GradeDirectorRepository(session).list_directors_in_school(
            course.school_id
        ):
            if user.is_active:
                candidates[user.id] = user

        if course.teacher_id is not None and course.teacher_id not in candidates:
            current = UserRepository(session).get_by_id(course.teacher_id)
            if current is not None:
                candidates[current.id] = current

        return [
            UserRead.model_validate(u).model_copy(
                update={"roles": role_repo.get_role_names_for_user(u.id)}
            )
            for u in sorted(
                candidates.values(), key=lambda x: (x.first_name or "", x.last_name or "")
            )
        ]

    def assign_teacher(
        self,
        session: Session,
        course_id: int,
        teacher_id: int,
        requesting_user_id: int,
    ) -> LmsCourse:
        course = CourseRepository(session).get_by_id(course_id)
        if course is None:
            raise LookupError("Course not found")

        self._assert_admin_or_director(session, course.grade_id, requesting_user_id)

        # Un director puede dictar cursos: en RobotSchool la misma persona
        # coordina un grado y tiene curso a cargo.
        course = CourseRepository(session).set_teacher(course, teacher_id)

        _audit.log(
            session,
            user_id=requesting_user_id,
            action="academic.course.teacher_assigned",
            resource_type="lms_course",
            resource_id=str(course.id),
            payload={"teacher_id": teacher_id},
        )
        return course

    def list_course_students(
        self, session: Session, course_id: int, user_id: int
    ) -> list[User]:
        course = CourseRepository(session).get_by_id(course_id)
        if course is None:
            raise LookupError("Course not found")
        self._assert_admin_or_director_or_teacher(session, course, user_id)
        return CourseStudentRepository(session).get_students(course.id)

    def enroll_student(
        self,
        session: Session,
        course_id: int,
        user_id: int,
        requesting_user_id: int,
    ) -> None:
        course = CourseRepository(session).get_by_id(course_id)
        if course is None:
            raise LookupError("Course not found")

        self._assert_admin_or_director_or_teacher(session, course, requesting_user_id)

        if course.teacher_id == user_id:
            raise ValueError("Cannot enroll the teacher of this course as a student")
        if GradeDirectorRepository(session).is_director_of_grade(
            course.grade_id, user_id
        ):
            raise ValueError("Cannot enroll a director as a student")

        cs_repo = CourseStudentRepository(session)
        if cs_repo.is_enrolled(course_id, user_id):
            raise ValueError("Already enrolled")

        cs_repo.enroll(course_id, user_id)

    def unenroll_student(
        self,
        session: Session,
        course_id: int,
        user_id: int,
        requesting_user_id: int,
    ) -> None:
        course = CourseRepository(session).get_by_id(course_id)
        if course is None:
            raise LookupError("Course not found")
        self._assert_admin_or_director(session, course.grade_id, requesting_user_id)
        if not CourseStudentRepository(session).unenroll(course_id, user_id):
            raise LookupError("Student is not enrolled")
        _audit.log(
            session,
            user_id=requesting_user_id,
            action="academic.student.unenrolled",
            resource_type="lms_course_student",
            resource_id=str(user_id),
            payload={"course_id": course_id},
        )

    def transfer_student(
        self,
        session: Session,
        student_id: int,
        from_course_id: int,
        to_course_id: int,
        requesting_user_id: int,
    ) -> None:
        from_course = CourseRepository(session).get_by_id(from_course_id)
        to_course = CourseRepository(session).get_by_id(to_course_id)
        if from_course is None or to_course is None:
            raise LookupError("Course not found")

        if from_course.grade_id != to_course.grade_id:
            raise ValueError("Both courses must belong to the same grade")

        self._assert_admin_or_director(
            session, from_course.grade_id, requesting_user_id
        )

        cs_repo = CourseStudentRepository(session)
        cs_repo.unenroll(from_course_id, student_id)
        cs_repo.enroll(to_course_id, student_id, from_course_id=from_course_id)

        _audit.log(
            session,
            user_id=requesting_user_id,
            action="academic.student.transferred",
            resource_type="lms_course_student",
            resource_id=str(student_id),
            payload={
                "from_course_id": from_course_id,
                "to_course_id": to_course_id,
            },
        )

    # ── Content ──────────────────────────────────────────────────────────────

    def create_unit(
        self,
        session: Session,
        course_id: int,
        data: UnitCreate,
        requesting_user_id: int,
    ) -> LmsUnit:
        course = CourseRepository(session).get_by_id(course_id)
        if course is None:
            raise LookupError("Course not found")
        self._assert_admin_or_teacher(session, course, requesting_user_id)
        return UnitRepository(session).create(course_id, data)

    def update_unit(
        self, session: Session, unit_id: int, data: UnitUpdate, user_id: int
    ) -> LmsUnit:
        unit = UnitRepository(session).get_by_id(unit_id)
        if unit is None:
            raise LookupError("Unit not found")
        course = CourseRepository(session).get_by_id(unit.course_id)
        self._assert_admin_or_teacher(session, course, user_id)
        return UnitRepository(session).update(unit, data)

    def add_material(
        self,
        session: Session,
        unit_id: int,
        data: MaterialCreate,
        file_bytes: bytes | None,
        content_type: str | None,
        requesting_user_id: int,
    ) -> LmsMaterial:
        unit = UnitRepository(session).get_by_id(unit_id)
        if unit is None:
            raise LookupError("Unit not found")
        course = CourseRepository(session).get_by_id(unit.course_id)
        self._assert_admin_or_teacher(session, course, requesting_user_id)

        file_key = None
        if data.type == "PDF" and file_bytes is not None:
            file_key = f"academic/{course.id}/materials/{uuid4()}.pdf"
            storage_service.upload_file(
                file_bytes, file_key, content_type or "application/pdf"
            )

        return MaterialRepository(session).create(unit_id, data, file_key=file_key)

    def add_material_from_repository(
        self,
        session: Session,
        unit_id: int,
        title: str,
        repository_file_public_id: str,
        requesting_user: User,
    ) -> LmsMaterial:
        unit = UnitRepository(session).get_by_id(unit_id)
        if unit is None:
            raise LookupError("Unit not found")
        course = CourseRepository(session).get_by_id(unit.course_id)
        self._assert_admin_or_teacher(session, course, requesting_user.id)

        try:
            # public_id del repositorio es String(36); normaliza el formato UUID
            # (minúsculas con guiones) para casar con lo almacenado.
            file_public_id = str(UUID(str(repository_file_public_id)))
        except (ValueError, TypeError):
            raise ValueError("Identificador de archivo inválido")

        repo_file = session.exec(
            select(RepositoryFile).where(RepositoryFile.public_id == file_public_id)
        ).first()
        if repo_file is None:
            raise LookupError("Archivo no encontrado en el repositorio")

        # El docente solo puede tomar archivos del repositorio que tiene permiso
        # de ver (por línea/colegio). El listado del picker ya filtra, pero la
        # verificación va también aquí: ocultar solo en la UI daría falsa
        # privacidad.
        scopes = get_user_scopes(session, requesting_user)
        if not can_see_file(session, repo_file, requesting_user, scopes):
            raise PermissionError("No tienes acceso a este archivo del repositorio")

        # Reutiliza el mismo objeto en MinIO (no se duplica el archivo): el
        # material apunta al file_key del repositorio.
        ext = (repo_file.file_type or "").lower().lstrip(".")
        material_type = "PDF" if ext == "pdf" else "FILE"

        existing = MaterialRepository(session).list_by_unit(unit_id)
        data = MaterialCreate(
            title=title.strip() or repo_file.name,
            type=material_type,
            order_index=len(existing),
        )
        return MaterialRepository(session).create(
            unit_id,
            data,
            file_key=repo_file.file_key,
            file_name=repo_file.file_name,
        )

    def get_material_deletion_impact(
        self,
        session: Session,
        material_id: int,
        requesting_user_id: int,
    ) -> dict:
        """Qué se pierde al borrar el material. Alimenta la confirmación de la UI.

        `pdf_annotations.material_id` es CASCADE en la BD (el modelo no lo
        declara, pero el DDL de prod sí), así que las anotaciones se van con el
        material. No bloquean el borrado: son notas personales de estudio, no
        trabajo calificado — a diferencia de las entregas de una tarea.
        """
        material = MaterialRepository(session).get_by_id(material_id)
        if material is None:
            raise LookupError("Material not found")
        unit = UnitRepository(session).get_by_id(material.unit_id)
        course = CourseRepository(session).get_by_id(unit.course_id)
        self._assert_admin_or_teacher(session, course, requesting_user_id)

        annotations = len(
            session.exec(
                select(PdfAnnotation).where(PdfAnnotation.material_id == material.id)
            ).all()
        )
        return {
            "title": material.title,
            "annotations": annotations,
            # El archivo del repositorio es compartido: se conserva.
            "deletes_file": bool(
                material.file_key and material.file_key.startswith("academic/")
            ),
            "can_delete": True,
        }

    def delete_material(
        self,
        session: Session,
        material_id: int,
        requesting_user_id: int,
    ) -> None:
        repo = MaterialRepository(session)
        material = repo.get_by_id(material_id)
        if material is None:
            raise LookupError("Material not found")
        unit = UnitRepository(session).get_by_id(material.unit_id)
        course = CourseRepository(session).get_by_id(unit.course_id)
        self._assert_admin_or_teacher(session, course, requesting_user_id)

        impact = self.get_material_deletion_impact(
            session, material.id, requesting_user_id
        )

        # Solo borrar el objeto en MinIO si es propio de academic. Los materiales
        # tomados del repositorio reutilizan el file_key del repositorio
        # (prefijo "repository/"): borrarlo dejaría rota la fuente y cualquier
        # otra referencia compartida.
        if material.file_key and material.file_key.startswith("academic/"):
            storage_service.delete_file(material.file_key)

        # Capturar antes del delete: después el objeto queda expirado.
        payload = {
            "title": material.title,
            "unit_id": material.unit_id,
            "course_id": course.id,
            "file_key": material.file_key,
            "cascaded": {"annotations": impact["annotations"]},
        }
        material_id_val = material.id

        repo.delete(material)

        _audit.log(
            session,
            user_id=requesting_user_id,
            action="academic.material.deleted",
            resource_type="lms_material",
            resource_id=str(material_id_val),
            payload=payload,
        )

    def get_assignment_deletion_impact(
        self,
        session: Session,
        assignment_id: int,
        requesting_user_id: int,
    ) -> dict:
        """Qué se destruiría al borrar la tarea. Alimenta la confirmación de la UI.

        Verificado contra las FKs de prod: borrar `lms_assignments` arrastra
        lms_submissions y rubrics → rubric_criteria → rubric_levels.
        """
        assignment = AssignmentRepository(session).get_by_id(assignment_id)
        if assignment is None:
            raise LookupError("Assignment not found")
        unit = UnitRepository(session).get_by_id(assignment.unit_id)
        course = CourseRepository(session).get_by_id(unit.course_id)
        self._assert_admin_or_teacher(session, course, requesting_user_id)

        submission_rows = session.exec(
            select(LmsSubmission).where(LmsSubmission.assignment_id == assignment.id)
        ).all()
        graded = len(
            [s for s in submission_rows if s.status == SubmissionStatus.GRADED]
        )
        rubrics = len(
            session.exec(
                select(Rubric).where(Rubric.lms_assignment_id == assignment.id)
            ).all()
        )

        return {
            "title": assignment.title,
            "submissions": len(submission_rows),
            "graded_submissions": graded,
            "rubrics": rubrics,
            # Misma regla que delete_course: el trabajo entregado por un
            # estudiante no se puede reconstruir, así que lo protege.
            "can_delete": len(submission_rows) == 0,
        }

    def delete_assignment(
        self,
        session: Session,
        assignment_id: int,
        requesting_user_id: int,
    ) -> None:
        repo = AssignmentRepository(session)
        assignment = repo.get_by_id(assignment_id)
        if assignment is None:
            raise LookupError("Assignment not found")
        unit = UnitRepository(session).get_by_id(assignment.unit_id)
        course = CourseRepository(session).get_by_id(unit.course_id)
        self._assert_admin_or_teacher(session, course, requesting_user_id)

        impact = self.get_assignment_deletion_impact(
            session, assignment.id, requesting_user_id
        )
        # Guarda anti-cascada, igual que en delete_course: la rúbrica se puede
        # rehacer; las ENTREGAS de los estudiantes no.
        if impact["submissions"]:
            raise ValueError(
                f"No se puede eliminar una tarea con entregas de estudiantes "
                f"({impact['submissions']}). El trabajo entregado no se puede "
                f"recuperar. Despublica la tarea en vez de eliminarla."
            )

        payload = {
            "title": assignment.title,
            "unit_id": assignment.unit_id,
            "course_id": course.id,
            "cascaded": {"rubrics": impact["rubrics"]},
        }
        assignment_id_val = assignment.id

        repo.delete(assignment)

        _audit.log(
            session,
            user_id=requesting_user_id,
            action="academic.assignment.deleted",
            resource_type="lms_assignment",
            resource_id=str(assignment_id_val),
            payload=payload,
        )

    def publish_material(
        self,
        session: Session,
        material_id: int,
        requesting_user_id: int,
        publish: bool = True,
    ) -> LmsMaterial:
        repo = MaterialRepository(session)
        material = repo.get_by_id(material_id)
        if material is None:
            raise LookupError("Material not found")
        unit = UnitRepository(session).get_by_id(material.unit_id)
        course = CourseRepository(session).get_by_id(unit.course_id)
        self._assert_admin_or_teacher(session, course, requesting_user_id)
        if publish:
            return repo.publish(material)
        return repo.unpublish(material)

    # ── Material access ─────────────────────────────────────────────────────

    def get_material_view_url(
        self,
        session: Session,
        material_id: int,
        requesting_user_id: int,
    ) -> dict[str, str]:
        material = MaterialRepository(session).get_by_id(material_id)
        if material is None:
            raise LookupError("Material no encontrado")
        if not material.file_key:
            raise ValueError("Este material no tiene archivo")

        unit = UnitRepository(session).get_by_id(material.unit_id)
        course = CourseRepository(session).get_by_id(unit.course_id)

        is_admin = self._is_admin(session, requesting_user_id)
        is_teacher = course.teacher_id == requesting_user_id

        if not is_admin and not is_teacher:
            if not material.is_published:
                raise PermissionError("Material no disponible")

        url = storage_service.generate_presigned_url(material.file_key, inline=True)
        return {"url": url, "file_name": material.file_name}

    def get_material_download_url(
        self,
        session: Session,
        material_id: int,
        requesting_user_id: int,
    ) -> dict[str, str]:
        material = MaterialRepository(session).get_by_id(material_id)
        if material is None:
            raise LookupError("Material not found")
        if not material.file_key:
            raise ValueError("Material has no file")

        if not self._is_admin(session, requesting_user_id):
            raise PermissionError("Solo administradores pueden descargar archivos")

        url = storage_service.generate_presigned_url(material.file_key, inline=False)
        return {"url": url}

    def publish_unit(
        self,
        session: Session,
        unit_id: int,
        requesting_user_id: int,
        publish: bool = True,
    ) -> LmsUnit:
        repo = UnitRepository(session)
        unit = repo.get_by_id(unit_id)
        if unit is None:
            raise LookupError("Unit not found")
        course = CourseRepository(session).get_by_id(unit.course_id)
        self._assert_admin_or_teacher(session, course, requesting_user_id)
        if publish:
            return repo.publish(unit)
        return repo.unpublish(unit)

    def create_assignment(
        self,
        session: Session,
        unit_id: int,
        data: AssignmentCreate,
        requesting_user_id: int,
    ) -> LmsAssignment:
        unit = UnitRepository(session).get_by_id(unit_id)
        if unit is None:
            raise LookupError("Unit not found")
        course = CourseRepository(session).get_by_id(unit.course_id)
        self._assert_admin_or_teacher(session, course, requesting_user_id)
        return AssignmentRepository(session).create(unit_id, data)

    def update_assignment(
        self, session: Session, assignment_id: int, data: AssignmentUpdate, user_id: int
    ) -> LmsAssignment:
        assignment = AssignmentRepository(session).get_by_id(assignment_id)
        if assignment is None:
            raise LookupError("Assignment not found")
        unit = UnitRepository(session).get_by_id(assignment.unit_id)
        course = CourseRepository(session).get_by_id(unit.course_id)
        self._assert_admin_or_teacher(session, course, user_id)
        return AssignmentRepository(session).update(assignment, data)

    def publish_assignment(
        self,
        session: Session,
        assignment_id: int,
        requesting_user_id: int,
        publish: bool = True,
    ) -> LmsAssignment:
        repo = AssignmentRepository(session)
        assignment = repo.get_by_id(assignment_id)
        if assignment is None:
            raise LookupError("Assignment not found")
        unit = UnitRepository(session).get_by_id(assignment.unit_id)
        course = CourseRepository(session).get_by_id(unit.course_id)
        self._assert_admin_or_teacher(session, course, requesting_user_id)
        return repo.update(assignment, AssignmentUpdate(is_published=publish))

    def get_assignment_submissions(
        self, session: Session, assignment_id: int, user_id: int
    ) -> list[tuple[LmsSubmission, User]]:
        assignment = AssignmentRepository(session).get_by_id(assignment_id)
        if assignment is None:
            raise LookupError("Assignment not found")
        unit = UnitRepository(session).get_by_id(assignment.unit_id)
        course = CourseRepository(session).get_by_id(unit.course_id)
        self._assert_admin_or_teacher(session, course, user_id)
        return SubmissionRepository(session).get_by_assignment(assignment.id)

    # ── Submissions ──────────────────────────────────────────────────────────

    def submit(
        self,
        session: Session,
        assignment_id: int,
        student_id: int,
        content: str | None,
        file_bytes: bytes | None,
        file_name: str | None,
        content_type: str | None,
    ) -> LmsSubmission:
        assignment = AssignmentRepository(session).get_by_id(assignment_id)
        if assignment is None:
            raise LookupError("Assignment not found")

        if not assignment.is_published:
            raise ValueError("Assignment not published")

        unit = UnitRepository(session).get_by_id(assignment.unit_id)
        course = CourseRepository(session).get_by_id(unit.course_id)

        if not CourseStudentRepository(session).is_enrolled(course.id, student_id):
            raise PermissionError("Student is not enrolled in this course")

        existing = SubmissionRepository(session).get_by_student_and_assignment(
            student_id, assignment_id
        )
        if existing and existing.status == SubmissionStatus.GRADED:
            raise ValueError("Cannot modify a graded submission")

        file_key = None
        if file_bytes is not None and file_name is not None:
            ext = file_name.rsplit(".", 1)[-1]
            key = (
                f"academic/{course.id}/submissions"
                f"/{assignment_id}/{student_id}/{uuid4()}.{ext}"
            )
            storage_service.upload_file(
                file_bytes, key, content_type or "application/octet-stream"
            )
            file_key = key

        return SubmissionRepository(session).upsert(
            assignment_id=assignment_id,
            student_id=student_id,
            content=content,
            file_key=file_key,
            file_name=file_name,
        )

    # ── Grading ──────────────────────────────────────────────────────────────

    def grade_submission(
        self,
        session: Session,
        submission_id: int,
        score: int,
        feedback: str | None,
        teacher_id: int,
    ) -> LmsSubmission:
        sub_repo = SubmissionRepository(session)
        submission = sub_repo.get_by_id(submission_id)
        if submission is None:
            raise LookupError("Submission not found")

        assignment = AssignmentRepository(session).get_by_id(submission.assignment_id)
        unit = UnitRepository(session).get_by_id(assignment.unit_id)
        course = CourseRepository(session).get_by_id(unit.course_id)
        self._assert_admin_or_teacher(session, course, teacher_id)

        if score < 0 or score > assignment.max_score:
            raise ValueError(
                f"Score must be between 0 and {assignment.max_score}"
            )

        submission = sub_repo.update(
            submission,
            SubmissionUpdate(
                status=SubmissionStatus.GRADED,
                score=score,
                feedback=feedback,
                graded_by=teacher_id,
                graded_at=datetime.now(timezone.utc),
            ),
        )

        _audit.log(
            session,
            user_id=teacher_id,
            action="academic.submission.graded",
            resource_type="lms_submission",
            resource_id=str(submission.id),
            payload={"score": score, "assignment_id": assignment.id},
        )
        return submission

    # ── Submission access ───────────────────────────────────────────────────

    def get_submission_view_url(
        self,
        session: Session,
        submission_id: int,
        requesting_user_id: int,
    ) -> dict[str, str]:
        submission = SubmissionRepository(session).get_by_id(submission_id)
        if submission is None:
            raise LookupError("Entrega no encontrada")

        is_owner = submission.student_id == requesting_user_id
        is_admin = self._is_admin(session, requesting_user_id)

        if not is_owner and not is_admin:
            assignment = AssignmentRepository(session).get_by_id(submission.assignment_id)
            unit = UnitRepository(session).get_by_id(assignment.unit_id)
            course = CourseRepository(session).get_by_id(unit.course_id)
            if course.teacher_id != requesting_user_id:
                raise PermissionError("Sin acceso a esta entrega")

        if not submission.file_key:
            raise ValueError("Esta entrega no tiene archivo adjunto")

        url = storage_service.generate_presigned_url(
            submission.file_key, expires_seconds=3600, inline=True
        )
        return {
            "url": url,
            "file_name": submission.file_name,
            "content_type": self._detect_content_type(submission.file_name),
        }

    def get_submission_download_url(
        self,
        session: Session,
        submission_id: int,
        requesting_user_id: int,
    ) -> dict[str, str]:
        submission = SubmissionRepository(session).get_by_id(submission_id)
        if submission is None:
            raise LookupError("Entrega no encontrada")

        if not self._is_admin(session, requesting_user_id):
            raise PermissionError("Solo administradores pueden descargar entregas")

        if not submission.file_key:
            raise ValueError("Esta entrega no tiene archivo adjunto")

        url = storage_service.generate_presigned_url(
            submission.file_key, expires_seconds=3600, inline=False
        )
        return {"url": url, "file_name": submission.file_name}

    # ── Gradebook ──────────────────────────────────────────────────────────

    # Los tres logros y el orden en que se muestran en la planilla / CSV.
    LOGROS = ("disenar", "programar", "robotizar")

    @staticmethod
    def _qualitative_level(pct: float | None) -> str | None:
        """Traduce un porcentaje (0–100) a la escala cualitativa del equipo.

        Cortes acordados: Excelente ≥90 · Bueno 75–89 · Regular 60–74 ·
        Insuficiente <60.
        """
        if pct is None:
            return None
        if pct >= 90:
            return "excelente"
        if pct >= 75:
            return "bueno"
        if pct >= 60:
            return "regular"
        return "insuficiente"

    def get_gradebook(
        self,
        session: Session,
        course_id: int,
        requesting_user_id: int,
    ) -> dict:
        course = CourseRepository(session).get_by_id(course_id)
        if course is None:
            raise LookupError("Curso no encontrado")

        self._assert_admin_or_director_or_teacher(session, course, requesting_user_id)

        assignments = AssignmentRepository(session).list_by_course(course.id)
        students = CourseStudentRepository(session).get_students(course.id)

        result_students = []
        for student in students:
            grades = {}
            scores: list[int] = []
            # Porcentajes (score/max_score) acumulados por logro, para promediar
            # cada logro sobre una base normalizada (tolera tareas 0–5 y 0–100).
            logro_pcts: dict[str, list[float]] = {lg: [] for lg in self.LOGROS}
            for assignment in assignments:
                sub = SubmissionRepository(session).get_by_student_and_assignment(
                    student.id, assignment.id
                )
                if sub:
                    grades[str(assignment.public_id)] = {
                        "score": sub.score,
                        "status": sub.status,
                        "submission_public_id": str(sub.public_id),
                    }
                    if sub.score is not None:
                        scores.append(sub.score)
                        if assignment.logro in logro_pcts and assignment.max_score:
                            logro_pcts[assignment.logro].append(
                                sub.score / assignment.max_score * 100
                            )
                else:
                    grades[str(assignment.public_id)] = None

            # Promedio y nivel de cada logro; None si aún no tiene notas.
            logros_result: dict[str, dict] = {}
            logro_averages: list[float] = []
            for lg in self.LOGROS:
                pcts = logro_pcts[lg]
                avg_pct = round(sum(pcts) / len(pcts), 1) if pcts else None
                if avg_pct is not None:
                    logro_averages.append(avg_pct)
                logros_result[lg] = {
                    "average_pct": avg_pct,
                    "level": self._qualitative_level(avg_pct),
                    "count": len(pcts),
                }

            # Definitiva = promedio simple de los logros que ya tienen datos.
            definitiva = (
                round(sum(logro_averages) / len(logro_averages), 1)
                if logro_averages
                else None
            )

            average = round(sum(scores) / len(scores), 1) if scores else None
            result_students.append({
                "student": {
                    "public_id": str(student.public_id),
                    "first_name": student.first_name,
                    "last_name": student.last_name,
                    "email": student.email,
                },
                "grades": grades,
                "logros": logros_result,
                "definitiva": definitiva,
                "definitiva_level": self._qualitative_level(definitiva),
                "average": average,
                "completed": len(scores),
                "total": len(assignments),
            })

        return {
            "course": {"public_id": str(course.public_id), "name": course.name},
            "assignments": [
                {
                    "public_id": str(a.public_id),
                    "title": a.title,
                    "max_score": a.max_score,
                    "logro": a.logro,
                    "due_date": str(a.due_date) if a.due_date else None,
                }
                for a in assignments
            ],
            "students": result_students,
        }

    # ── Queries ──────────────────────────────────────────────────────────────

    def get_my_courses_as_teacher(
        self, session: Session, user_id: int
    ) -> list[LmsCourse]:
        if self._is_admin(session, user_id):
            return CourseRepository(session).list_all_active()
        director_grades = GradeDirectorRepository(session).get_grades_for_director(
            user_id
        )
        if director_grades:
            grade_ids = [g.id for g in director_grades]
            return CourseRepository(session).list_by_grade_ids(grade_ids)
        return CourseRepository(session).list_by_teacher(user_id)

    def get_my_courses_as_student(
        self, session: Session, user_id: int
    ) -> list[LmsCourse]:
        if self._is_admin(session, user_id):
            return []
        return CourseStudentRepository(session).get_courses_for_student(user_id)

    def get_my_grades_as_director(
        self, session: Session, user_id: int
    ) -> list[LmsGrade]:
        if self._is_admin(session, user_id):
            return GradeRepository(session).list_all_active()
        return GradeDirectorRepository(session).get_grades_for_director(user_id)

    def get_course_content(
        self,
        session: Session,
        course_id: int,
        requesting_user_id: int,
    ) -> tuple[
        LmsCourse,
        list[
            tuple[
                LmsUnit,
                list[LmsMaterial],
                list[tuple[LmsAssignment, LmsSubmission | None]],
            ]
        ],
    ]:
        course = CourseRepository(session).get_by_id(course_id)
        if course is None:
            raise LookupError("Course not found")

        is_admin = self._is_admin(session, requesting_user_id)
        is_teacher = course.teacher_id == requesting_user_id
        is_director = GradeDirectorRepository(session).is_director_of_grade(
            course.grade_id, requesting_user_id
        )
        is_student = CourseStudentRepository(session).is_enrolled(
            course_id, requesting_user_id
        )

        if not (is_admin or is_teacher or is_director or is_student):
            raise PermissionError(
                "User must be admin, teacher, director, or enrolled student"
            )

        published_only = not (is_admin or is_teacher)

        units = UnitRepository(session).list_by_course(
            course_id, published_only=published_only
        )
        result: list[
            tuple[
                LmsUnit,
                list[LmsMaterial],
                list[tuple[LmsAssignment, LmsSubmission | None]],
            ]
        ] = []
        for unit in units:
            materials = MaterialRepository(session).list_by_unit(
                unit.id, published_only=published_only
            )
            assignments = AssignmentRepository(session).list_by_unit(
                unit.id, published_only=published_only
            )
            assignment_data: list[tuple[LmsAssignment, LmsSubmission | None]] = []
            for a in assignments:
                sub = None
                if is_student:
                    sub = SubmissionRepository(session).get_by_student_and_assignment(
                        requesting_user_id, a.id
                    )
                assignment_data.append((a, sub))
            result.append((unit, materials, assignment_data))

        return course, result

    # ── PDF Annotations ─────────────────────────────────────────────────────

    def get_annotations(
        self, session: Session, material_id: UUID, requesting_user_id: int
    ) -> dict:
        material = MaterialRepository(session).get_by_public_id(material_id)
        if not material:
            raise LookupError("Material no encontrado")

        user = UserRepository(session).get_by_id(requesting_user_id)

        annotation = PDFAnnotationRepository(session).get_by_user_and_material(
            user.id, material.id
        )

        return {"highlights": annotation.highlights if annotation else []}

    def save_annotations(
        self,
        session: Session,
        material_id: UUID,
        requesting_user_id: int,
        highlights: list,
    ) -> dict:
        material = MaterialRepository(session).get_by_public_id(material_id)
        if not material:
            raise LookupError("Material no encontrado")

        user = UserRepository(session).get_by_id(requesting_user_id)

        if len(highlights) > 500:
            raise ValueError("Máximo 500 anotaciones por documento")

        annotation = PDFAnnotationRepository(session).upsert(
            user.id, material.id, highlights
        )
        return {"highlights": annotation.highlights}
