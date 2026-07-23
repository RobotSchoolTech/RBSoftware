from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Session, select

from app.core.identifiers import parse_public_id
from app.core.storage import storage_service, extension_of, safe_content_type
from app.domains.repository.models.repository_file import RepositoryFile
from app.domains.audit.services import AuditService
from app.domains.auth.repositories import UserRepository
from app.domains.rbac.repositories import UserRoleRepository
from app.domains.training.models.training_certificate import TrainingCertificate
from app.domains.training.models.training_enrollment import TrainingEnrollment
from app.domains.training.models.training_submission import (
    TrainingSubmission,
    TrainingSubmissionStatus,
)
from app.domains.training.repositories.certificate_repository import CertificateRepository
from app.domains.training.repositories.enrollment_repository import EnrollmentRepository
from app.domains.training.repositories.evaluation_repository import EvaluationRepository
from app.domains.training.repositories.lesson_progress_repository import LessonProgressRepository
from app.domains.training.repositories.lesson_repository import LessonRepository
from app.domains.training.repositories.module_repository import ModuleRepository
from app.domains.training.repositories.program_repository import ProgramRepository
from app.domains.training.repositories.quiz_question_repository import QuizQuestionRepository
from app.domains.training.repositories.submission_repository import SubmissionRepository
from app.domains.training.schemas.composite import TeacherProgramProgress
from app.domains.training.models.training_evaluation import TrainingEvaluation
from app.domains.training.schemas.training_evaluation import (
    EvaluationCreate,
    EvaluationRead,
    EvaluationUpdate,
)
from app.domains.training.schemas.training_lesson import LessonCreate, LessonUpdate
from app.domains.training.schemas.training_module import ModuleCreate, ModuleUpdate
from app.domains.training.schemas.training_program import (
    ProgramCreate,
    ProgramUpdate,
)
from app.domains.training.schemas.training_quiz_question import (
    QuizQuestionCreate,
    QuizQuestionUpdate,
)

_audit = AuditService()

# Extensiones admitidas al subir el archivo de una lección, por tipo. Es un
# subconjunto de INLINE_SAFE_EXTENSIONS: lo que se admite subir tiene que poder
# servirse inline, porque el visor de lecciones lo abre embebido.
LESSON_FILE_EXTENSIONS = {
    "PDF": frozenset({"pdf"}),
    "VIDEO": frozenset({"mp4", "webm"}),
}


def resolve_lesson_file_extension(lesson_type: str, *names: str | None) -> str:
    """Extensión validada del archivo de una lección, o ValueError.

    La extensión sale del NOMBRE del archivo, nunca del content-type que declara
    el cliente: un `.html` anunciado como `application/pdf` terminaba guardado
    como text/html y el visor lo abría en un iframe (XSS almacenado same-origin).

    Cuando se conoce más de un nombre para el mismo archivo —el key que generó el
    servidor y el nombre que declaró el cliente— se exige que TODOS coincidan en
    una extensión admitida. Si divergen, el archivo no es lo que dice ser y no
    hay una de las dos fuentes que merezca más confianza que la otra.
    """
    allowed = LESSON_FILE_EXTENSIONS[lesson_type]
    extensions = {ext for ext in map(extension_of, names) if ext}
    if not extensions or not extensions <= allowed:
        raise ValueError(
            f"Una lección {lesson_type} solo admite archivos "
            f"{', '.join('.' + e for e in sorted(allowed))}"
        )
    return extensions.pop()


class TrainingService:

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _get_roles(session: Session, user_id: int) -> list[str]:
        return UserRoleRepository(session).get_role_names_for_user(user_id)

    @staticmethod
    def _is_admin(session: Session, user_id: int) -> bool:
        return "ADMIN" in UserRoleRepository(session).get_role_names_for_user(user_id)

    @staticmethod
    def _is_admin_or_trainer(session: Session, user_id: int) -> bool:
        roles = UserRoleRepository(session).get_role_names_for_user(user_id)
        return any(r in roles for r in ["ADMIN", "TRAINER", "SUPER_TRAINER"])

    def _assert_admin_or_trainer(self, session: Session, user_id: int) -> None:
        if not self._is_admin_or_trainer(session, user_id):
            raise PermissionError("Se requiere rol ADMIN o TRAINER")

    def _assert_admin(self, session: Session, user_id: int) -> None:
        if not self._is_admin(session, user_id):
            raise PermissionError("Se requiere rol ADMIN")

    @staticmethod
    def _is_admin_or_super_trainer(session: Session, user_id: int) -> bool:
        roles = UserRoleRepository(session).get_role_names_for_user(user_id)
        return "ADMIN" in roles or "SUPER_TRAINER" in roles

    def _assert_admin_or_super_trainer(self, session: Session, user_id: int) -> None:
        if not self._is_admin_or_super_trainer(session, user_id):
            raise PermissionError("Se requiere rol ADMIN o SUPER_TRAINER")

    # ── Program management ───────────────────────────────────────────────────

    def create_program(
        self,
        session: Session,
        data: ProgramCreate,
        requesting_user_id: int,
    ):
        self._assert_admin_or_trainer(session, requesting_user_id)
        return ProgramRepository(session).create(data, created_by=requesting_user_id)

    def update_program(
        self,
        session: Session,
        program_id: UUID,
        data: ProgramUpdate,
        requesting_user_id: int,
    ):
        self._assert_admin_or_trainer(session, requesting_user_id)
        program = ProgramRepository(session).get_by_public_id(program_id)
        if program is None:
            raise LookupError("Programa no encontrado")
        return ProgramRepository(session).update(program, data)

    def publish_program(
        self,
        session: Session,
        program_id: UUID,
        requesting_user_id: int,
        publish: bool = True,
    ):
        self._assert_admin_or_trainer(session, requesting_user_id)
        program = ProgramRepository(session).get_by_public_id(program_id)
        if program is None:
            raise LookupError("Programa no encontrado")

        if publish:
            modules = ModuleRepository(session).list_by_program(program.id)
            if not modules:
                raise ValueError(
                    "El programa debe tener al menos un módulo antes de publicar"
                )
            has_content = False
            for mod in modules:
                lessons = LessonRepository(session).list_by_module(mod.id)
                evals = EvaluationRepository(session).list_by_module(mod.id)
                if lessons or evals:
                    has_content = True
                    break
            if not has_content:
                raise ValueError(
                    "Al menos un módulo debe tener lecciones o evaluaciones antes de publicar"
                )

        program.is_published = publish
        session.add(program)
        session.commit()
        session.refresh(program)
        return program

    # ── Module management ────────────────────────────────────────────────────

    def create_module(
        self,
        session: Session,
        program_id: UUID,
        data: ModuleCreate,
        requesting_user_id: int,
    ):
        self._assert_admin_or_trainer(session, requesting_user_id)
        program = ProgramRepository(session).get_by_public_id(program_id)
        if program is None:
            raise LookupError("Programa no encontrado")
        return ModuleRepository(session).create(program.id, data)

    # ── Lesson management ────────────────────────────────────────────────────

    def create_lesson(
        self,
        session: Session,
        module_id: UUID,
        data: LessonCreate,
        file_bytes: bytes | None,
        file_name: str | None,
        requesting_user_id: int,
    ):
        self._assert_admin_or_trainer(session, requesting_user_id)
        module = ModuleRepository(session).get_by_public_id(module_id)
        if module is None:
            raise LookupError("Módulo no encontrado")

        file_key = None
        if data.type in ("PDF", "VIDEO") and file_bytes is not None:
            ext = resolve_lesson_file_extension(data.type, file_name)
            file_key = f"training/{module.program_id}/lessons/{uuid4()}.{ext}"
            # Content-type anclado desde la extensión, NUNCA del cliente.
            storage_service.upload_file(
                file_bytes, file_key, safe_content_type(file_key)
            )

        existing = LessonRepository(session).list_by_module(module.id)
        overrides: dict = {"order_index": len(existing)}
        if file_key:
            overrides["file_key"] = file_key
        data_with_file = LessonCreate.model_validate(data.model_dump() | overrides)
        return LessonRepository(session).create(module.id, data_with_file)

    def create_lesson_from_repository(
        self,
        session: Session,
        module_id: UUID,
        data: LessonCreate,
        repository_file_public_id: str,
        requesting_user_id: int,
    ):
        self._assert_admin_or_trainer(session, requesting_user_id)
        module = ModuleRepository(session).get_by_public_id(module_id)
        if module is None:
            raise LookupError("Módulo no encontrado")

        repo_file = session.exec(
            select(RepositoryFile).where(
                RepositoryFile.public_id == repository_file_public_id
            )
        ).first()
        if repo_file is None:
            raise LookupError("Archivo no encontrado en repositorio")

        if data.type not in ("PDF", "VIDEO"):
            raise ValueError("El tipo debe ser PDF o VIDEO")

        # El repositorio admite cualquier extensión, así que la lección hereda un
        # archivo no controlado: se valida igual que en la subida directa. Sin
        # esto la lección quedaría creada pero el visor no podría mostrarla (el
        # servido seguro la degradaría a descarga).
        resolve_lesson_file_extension(
            data.type, repo_file.file_key, repo_file.file_name
        )

        existing = LessonRepository(session).list_by_module(module.id)
        data_with_file = LessonCreate.model_validate(
            data.model_dump()
            | {"order_index": len(existing), "file_key": repo_file.file_key}
        )
        return LessonRepository(session).create(module.id, data_with_file)

    # ── Evaluation management ────────────────────────────────────────────────

    def create_evaluation(
        self,
        session: Session,
        module_id: UUID,
        data: EvaluationCreate,
        requesting_user_id: int,
    ):
        self._assert_admin_or_trainer(session, requesting_user_id)
        module = ModuleRepository(session).get_by_public_id(module_id)
        if module is None:
            raise LookupError("Módulo no encontrado")
        return EvaluationRepository(session).create(module.id, data)

    def update_evaluation(
        self,
        session: Session,
        evaluation_id: UUID,
        data: EvaluationUpdate,
        requesting_user_id: int,
    ) -> TrainingEvaluation:
        self._assert_admin_or_trainer(session, requesting_user_id)
        evaluation = EvaluationRepository(session).get_by_public_id(evaluation_id)
        if evaluation is None:
            raise LookupError("Evaluación no encontrada")

        updates = data.model_dump(exclude_unset=True)

        if "after_lesson_public_id" in updates:
            public_id = updates.pop("after_lesson_public_id")
            if public_id is None:
                evaluation.after_lesson_id = None
            else:
                lesson = LessonRepository(session).get_by_public_id(parse_public_id(public_id, detail="ID de lección inválido"))
                if lesson is None:
                    raise LookupError("Lección no encontrada")
                if lesson.module_id != evaluation.module_id:
                    raise ValueError(
                        "La lección no pertenece al mismo módulo de la evaluación"
                    )
                evaluation.after_lesson_id = lesson.id

        for field_name, value in updates.items():
            setattr(evaluation, field_name, value)

        session.add(evaluation)
        session.commit()
        session.refresh(evaluation)
        return evaluation

    @staticmethod
    def build_evaluation_read(
        session: Session, evaluation: TrainingEvaluation
    ) -> EvaluationRead:
        after_lesson_public_id: str | None = None
        if evaluation.after_lesson_id is not None:
            lesson = LessonRepository(session).get(evaluation.after_lesson_id)
            if lesson is not None:
                after_lesson_public_id = str(lesson.public_id)
        return EvaluationRead.model_validate(
            {
                **evaluation.model_dump(),
                "after_lesson_public_id": after_lesson_public_id,
            }
        )

    # ── Quiz question management ─────────────────────────────────────────────

    def create_quiz_question(
        self,
        session: Session,
        evaluation_id: UUID,
        data: QuizQuestionCreate,
        requesting_user_id: int,
    ):
        self._assert_admin_or_trainer(session, requesting_user_id)
        evaluation = EvaluationRepository(session).get_by_public_id(evaluation_id)
        if evaluation is None:
            raise LookupError("Evaluación no encontrada")
        if len(data.options) != 4:
            raise ValueError("Se requieren exactamente 4 opciones")
        if data.correct_option not in (0, 1, 2, 3):
            raise ValueError("correct_option debe estar entre 0 y 3")
        question = QuizQuestionRepository(session).create(evaluation.id, data)
        questions = QuizQuestionRepository(session).list_by_evaluation(evaluation.id)
        evaluation.max_score = sum(q.points for q in questions)
        session.add(evaluation)
        session.commit()
        return question

    # ── Enrollments ──────────────────────────────────────────────────────────

    def enroll_teacher(
        self,
        session: Session,
        program_id: UUID,
        user_id: int,
        requesting_user_id: int,
    ):
        self._assert_admin_or_trainer(session, requesting_user_id)
        program = ProgramRepository(session).get_by_public_id(program_id)
        if program is None:
            raise LookupError("Programa no encontrado")

        user = UserRepository(session).get_by_id(user_id)
        if user is None:
            raise LookupError("Usuario no encontrado")

        role_names = self._get_roles(session, user_id)
        if "TEACHER" not in role_names:
            raise ValueError("El usuario debe tener rol TEACHER")

        enrollment_repo = EnrollmentRepository(session)
        if enrollment_repo.is_enrolled(user_id, program.id):
            raise ValueError("El usuario ya está inscrito en este programa")

        enrollment = TrainingEnrollment(
            program_id=program.id,
            user_id=user_id,
            enrolled_by=requesting_user_id,
            enrolled_at=datetime.now(timezone.utc),
        )
        enrollment = enrollment_repo.create(enrollment)

        _audit.log(
            session,
            user_id=requesting_user_id,
            action="training.enrollment.created",
            resource_type="training_enrollment",
            resource_id=str(enrollment.id),
            payload={"program_id": program.id, "enrolled_user_id": user_id},
        )
        return enrollment

    # ── Teacher progress ─────────────────────────────────────────────────────

    def get_my_completed_lessons(
        self,
        session: Session,
        program_id: UUID,
        user_id: int,
    ) -> list[UUID]:
        program = ProgramRepository(session).get_by_public_id(program_id)
        if program is None:
            raise LookupError("Programa no encontrado")
        enrollment_repo = EnrollmentRepository(session)
        if not enrollment_repo.is_enrolled(user_id, program.id):
            raise PermissionError("El usuario no está inscrito en este programa")
        return LessonProgressRepository(session).get_completed_lesson_public_ids(
            user_id, program.id
        )

    def mark_lesson_completed(
        self,
        session: Session,
        lesson_id: UUID,
        user_id: int,
    ):
        lesson = LessonRepository(session).get_by_public_id(lesson_id)
        if lesson is None:
            raise LookupError("Lección no encontrada")

        module = ModuleRepository(session).get(lesson.module_id)
        enrollment_repo = EnrollmentRepository(session)
        if not enrollment_repo.is_enrolled(user_id, module.program_id):
            raise PermissionError("El usuario no está inscrito en este programa")

        return LessonProgressRepository(session).mark_completed(user_id, lesson.id)

    def submit_quiz(
        self,
        session: Session,
        evaluation_id: UUID,
        user_id: int,
        answers: dict[str, int],
    ):
        evaluation = EvaluationRepository(session).get_by_public_id(evaluation_id)
        if evaluation is None:
            raise LookupError("Evaluación no encontrada")

        module = ModuleRepository(session).get(evaluation.module_id)
        if not EnrollmentRepository(session).is_enrolled(user_id, module.program_id):
            raise PermissionError("El usuario no está inscrito en este programa")

        if evaluation.type != "QUIZ":
            raise ValueError("Esta evaluación no es de tipo QUIZ")

        questions = QuizQuestionRepository(session).list_by_evaluation(evaluation.id)
        if not questions:
            raise ValueError("La evaluación no tiene preguntas")

        total_points = sum(q.points for q in questions)
        score = sum(
            q.points
            for q in questions
            if answers.get(str(q.public_id)) == q.correct_option
        )
        passing_threshold = round(evaluation.passing_score * total_points / 100) if total_points > 0 else evaluation.passing_score

        now = datetime.now(timezone.utc)
        submission_repo = SubmissionRepository(session)

        existing = submission_repo.get_by_user_and_evaluation(user_id, evaluation.id)
        if existing is not None:
            if existing.status == TrainingSubmissionStatus.GRADED:
                if (
                    existing.score is not None
                    and existing.score >= passing_threshold
                ):
                    raise ValueError("Esta evaluación ya fue aprobada")
                if existing.attempts_used >= evaluation.max_attempts:
                    raise ValueError("Agotaste los intentos para esta evaluación")
            existing.quiz_answers = answers
            existing.score = max(existing.score or 0, score)
            existing.status = TrainingSubmissionStatus.GRADED
            existing.submitted_at = now
            existing.graded_at = now
            existing.attempts_used = existing.attempts_used + 1
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing

        submission = TrainingSubmission(
            evaluation_id=evaluation.id,
            user_id=user_id,
            quiz_answers=answers,
            score=score,
            status=TrainingSubmissionStatus.GRADED,
            submitted_at=now,
            graded_at=now,
            attempts_used=1,
        )
        session.add(submission)
        session.commit()
        session.refresh(submission)
        return submission

    def submit_practical(
        self,
        session: Session,
        evaluation_id: UUID,
        user_id: int,
        content: str | None,
        file_bytes: bytes | None,
        file_name: str | None,
    ):
        evaluation = EvaluationRepository(session).get_by_public_id(evaluation_id)
        if evaluation is None:
            raise LookupError("Evaluación no encontrada")

        module = ModuleRepository(session).get(evaluation.module_id)
        if not EnrollmentRepository(session).is_enrolled(user_id, module.program_id):
            raise PermissionError("El usuario no está inscrito en este programa")

        if evaluation.type != "PRACTICAL":
            raise ValueError("Esta evaluación no es de tipo PRACTICAL")

        file_key = None
        if file_bytes is not None and file_name is not None:
            ext = extension_of(file_name)
            suffix = f".{ext}" if ext else ""
            file_key = (
                f"training/{module.program_id}/submissions"
                f"/{evaluation.id}/{user_id}/{uuid4()}{suffix}"
            )
            # Content-type anclado desde la extensión, NUNCA del cliente: evita
            # guardar la entrega como text/html y servirla inline (XSS).
            storage_service.upload_file(
                file_bytes, file_key, safe_content_type(file_name)
            )

        result = SubmissionRepository(session).upsert(
            user_id,
            evaluation.id,
            content=content,
            file_key=file_key,
            file_name=file_name,
        )
        if result is None:
            raise ValueError("No se puede modificar una entrega ya calificada")
        return result

    def grade_practical(
        self,
        session: Session,
        submission_id: UUID,
        score: int,
        feedback: str | None,
        trainer_id: int,
    ):
        self._assert_admin_or_trainer(session, trainer_id)

        submission = SubmissionRepository(session).get_by_public_id(submission_id)
        if submission is None:
            raise LookupError("Entrega no encontrada")

        evaluation = EvaluationRepository(session).get(submission.evaluation_id)
        if score < 0 or score > evaluation.max_score:
            raise ValueError(
                f"El puntaje debe estar entre 0 y {evaluation.max_score}"
            )

        now = datetime.now(timezone.utc)
        submission.score = max(submission.score or 0, score)
        submission.feedback = feedback
        submission.status = TrainingSubmissionStatus.GRADED
        submission.graded_by = trainer_id
        submission.graded_at = now
        submission.attempts_used = submission.attempts_used + 1
        session.add(submission)
        session.commit()
        session.refresh(submission)

        _audit.log(
            session,
            user_id=trainer_id,
            action="training.submission.graded",
            resource_type="training_submission",
            resource_id=str(submission.id),
            payload={
                "score": score,
                "evaluation_id": evaluation.id,
            },
        )
        return submission

    # ── Certificates ─────────────────────────────────────────────────────────

    def check_completion(self, session: Session, enrollment_id: UUID) -> dict:
        enrollment = EnrollmentRepository(session).get_by_public_id(enrollment_id)
        if enrollment is None:
            raise LookupError("Inscripción no encontrada")

        modules = ModuleRepository(session).list_by_program(
            enrollment.program_id, published_only=True
        )

        lessons_total = 0
        evaluations_total = 0
        all_lessons: list[int] = []
        all_evaluations: list = []

        for mod in modules:
            lessons = LessonRepository(session).list_by_module(
                mod.id, published_only=True
            )
            evals = EvaluationRepository(session).list_by_module(
                mod.id, published_only=True
            )
            lessons_total += len(lessons)
            evaluations_total += len(evals)
            all_lessons.extend(l.id for l in lessons)
            all_evaluations.extend(evals)

        completed_ids = LessonProgressRepository(session).get_completed_lessons(
            enrollment.user_id, enrollment.program_id
        )
        lessons_completed = len(
            [lid for lid in all_lessons if lid in completed_ids]
        )

        evaluations_passed = 0
        scores: list[int] = []
        sub_repo = SubmissionRepository(session)
        quiz_q_repo = QuizQuestionRepository(session)
        for ev in all_evaluations:
            sub = sub_repo.get_by_user_and_evaluation(
                enrollment.user_id, ev.id
            )
            if sub and sub.status == TrainingSubmissionStatus.GRADED:
                if sub.score is not None:
                    scores.append(sub.score)
                    if ev.type == "QUIZ":
                        total_pts = sum(q.points for q in quiz_q_repo.list_by_evaluation(ev.id))
                        threshold = round(ev.passing_score * total_pts / 100) if total_pts > 0 else ev.passing_score
                    else:
                        threshold = ev.passing_score
                    if sub.score >= threshold:
                        evaluations_passed += 1

        average_score = round(sum(scores) / len(scores), 1) if scores else 0.0
        is_eligible = (
            evaluations_total > 0
            and evaluations_passed == evaluations_total
        )

        return {
            "lessons_completed": lessons_completed,
            "lessons_total": lessons_total,
            "evaluations_passed": evaluations_passed,
            "evaluations_total": evaluations_total,
            "average_score": average_score,
            "is_eligible": is_eligible,
        }

    def issue_certificate(
        self,
        session: Session,
        enrollment_id: UUID,
        requesting_user_id: int,
    ):
        self._assert_admin_or_super_trainer(session, requesting_user_id)

        enrollment = EnrollmentRepository(session).get_by_public_id(enrollment_id)
        if enrollment is None:
            raise LookupError("Inscripción no encontrada")

        completion = self.check_completion(session, enrollment_id)
        if not completion["is_eligible"]:
            raise ValueError(
                "El docente no ha completado todas las evaluaciones requeridas"
            )

        cert_repo = CertificateRepository(session)
        existing = cert_repo.get_by_enrollment(enrollment.id)
        if existing is not None:
            raise ValueError("Ya existe un certificado para esta inscripción")

        year = datetime.now(timezone.utc).year
        certificate_code = f"RS-{year}-{uuid4().hex[:8].upper()}"

        certificate = TrainingCertificate(
            enrollment_id=enrollment.id,
            user_id=enrollment.user_id,
            program_id=enrollment.program_id,
            issued_by=requesting_user_id,
            issued_at=datetime.now(timezone.utc),
            certificate_code=certificate_code,
        )
        certificate = cert_repo.create(certificate)

        enrollment.completed_at = datetime.now(timezone.utc)
        enrollment.status = "COMPLETED"
        session.add(enrollment)
        session.commit()
        session.refresh(enrollment)

        _audit.log(
            session,
            user_id=requesting_user_id,
            action="training.certificate.issued",
            resource_type="training_certificate",
            resource_id=str(certificate.id),
            payload={
                "enrollment_id": enrollment.id,
                "user_id": enrollment.user_id,
                "program_id": enrollment.program_id,
                "certificate_code": certificate_code,
            },
        )
        return certificate

    # ── Gradebook ─────────────────────────────────────────────────────────────

    def get_training_gradebook(
        self,
        session: Session,
        program_id: UUID,
        requesting_user_id: int,
    ) -> dict:
        program = ProgramRepository(session).get_by_public_id(program_id)
        if program is None:
            raise LookupError("Programa no encontrado")

        if not self._is_admin(session, requesting_user_id):
            roles = self._get_roles(session, requesting_user_id)
            if "TRAINER" not in roles or program.created_by != requesting_user_id:
                raise PermissionError("Solo ADMIN o el TRAINER creador pueden ver la planilla")

        modules = ModuleRepository(session).list_by_program(program.id)
        evaluations = []
        for mod in modules:
            evaluations.extend(EvaluationRepository(session).list_by_module(mod.id))

        enrollments = EnrollmentRepository(session).list_by_program(program.id)
        sub_repo = SubmissionRepository(session)
        cert_repo = CertificateRepository(session)

        result_teachers = []
        for enrollment in enrollments:
            from app.domains.auth.repositories import UserRepository

            teacher = UserRepository(session).get_by_id(enrollment.user_id)
            if teacher is None:
                continue

            grades: dict = {}
            scores: list[int] = []

            for ev in evaluations:
                sub = sub_repo.get_by_user_and_evaluation(enrollment.user_id, ev.id)
                if sub and sub.score is not None:
                    grades[str(ev.public_id)] = {
                        "score": sub.score,
                        "status": sub.status,
                        "submission_id": str(sub.public_id),
                        "type": ev.type,
                    }
                    scores.append(sub.score)
                else:
                    grades[str(ev.public_id)] = None

            average = round(sum(scores) / len(scores), 1) if scores else None

            result_teachers.append(
                {
                    "teacher": {
                        "public_id": str(teacher.public_id),
                        "first_name": teacher.first_name,
                        "last_name": teacher.last_name,
                        "email": teacher.email,
                    },
                    "grades": grades,
                    "average": average,
                    "completed": len(scores),
                    "total": len(evaluations),
                    "is_certified": cert_repo.get_by_enrollment(enrollment.id) is not None,
                }
            )

        return {
            "program": {
                "public_id": str(program.public_id),
                "name": program.name,
            },
            "evaluations": [
                {
                    "public_id": str(e.public_id),
                    "title": e.title,
                    "type": e.type,
                    "max_score": e.max_score,
                    "passing_score": e.passing_score,
                }
                for e in evaluations
            ],
            "teachers": result_teachers,
        }

    # ── Teacher progress view ────────────────────────────────────────────────

    def get_my_programs(
        self, session: Session, user_id: int
    ) -> list[TeacherProgramProgress]:
        enrollments = EnrollmentRepository(session).list_by_user(user_id)
        result: list[TeacherProgramProgress] = []

        for enrollment in enrollments:
            program = ProgramRepository(session).get(enrollment.program_id)
            if program is None:
                continue

            modules = ModuleRepository(session).list_by_program(
                program.id, published_only=True
            )

            total_lessons = 0
            total_evaluations = 0
            all_lesson_ids: list[int] = []
            all_evals: list = []

            for mod in modules:
                lessons = LessonRepository(session).list_by_module(
                    mod.id, published_only=True
                )
                evals = EvaluationRepository(session).list_by_module(
                    mod.id, published_only=True
                )
                total_lessons += len(lessons)
                total_evaluations += len(evals)
                all_lesson_ids.extend(l.id for l in lessons)
                all_evals.extend(evals)

            completed_ids = LessonProgressRepository(session).get_completed_lessons(
                user_id, program.id
            )
            completed_lessons = len(
                [lid for lid in all_lesson_ids if lid in completed_ids]
            )

            passed_evaluations = 0
            scores: list[int] = []
            sub_repo = SubmissionRepository(session)
            quiz_q_repo = QuizQuestionRepository(session)
            for ev in all_evals:
                sub = sub_repo.get_by_user_and_evaluation(user_id, ev.id)
                if sub and sub.status == TrainingSubmissionStatus.GRADED:
                    if sub.score is not None:
                        scores.append(sub.score)
                        if ev.type == "QUIZ":
                            total_pts = sum(q.points for q in quiz_q_repo.list_by_evaluation(ev.id))
                            threshold = round(ev.passing_score * total_pts / 100) if total_pts > 0 else ev.passing_score
                        else:
                            threshold = ev.passing_score
                        if sub.score >= threshold:
                            passed_evaluations += 1

            overall_score = round(sum(scores) / len(scores), 1) if scores else None

            cert = CertificateRepository(session).get_by_enrollment(enrollment.id)

            result.append(
                TeacherProgramProgress(
                    program_id=program.public_id,
                    program_name=program.name,
                    total_lessons=total_lessons,
                    completed_lessons=completed_lessons,
                    total_evaluations=total_evaluations,
                    passed_evaluations=passed_evaluations,
                    overall_score=overall_score,
                    is_certified=cert is not None,
                    certificate_code=cert.certificate_code if cert else None,
                )
            )

        return result
