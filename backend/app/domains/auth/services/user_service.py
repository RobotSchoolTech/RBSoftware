from __future__ import annotations

from uuid import UUID

from sqlmodel import Session

from app.core.security import hash_password, verify_password
from app.domains.auth.models import User
from app.domains.auth.repositories import UserRepository
from app.domains.auth.schemas import UserCreate, UserRead, UserUpdate
from app.domains.rbac.repositories import UserRoleRepository
from app.domains.auth.services.refresh_token_service import RefreshTokenService


class UserService:
    def register(
        self,
        session: Session,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        phone: str | None = None,
        position: str | None = None,
    ) -> User:
        repo = UserRepository(session)
        if repo.get_by_email(email) is not None:
            raise ValueError(f"Email already registered: {email}")
        return repo.create(
            UserCreate(
                email=email,
                password_hash=hash_password(password),
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                position=position,
            )
        )

    def authenticate(self, session: Session, email: str, password: str) -> User | None:
        repo = UserRepository(session)
        user = repo.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            return None
        return user

    def get_by_id(self, session: Session, user_id: int) -> User | None:
        return UserRepository(session).get_by_id(user_id)

    def get_by_public_id(self, session: Session, public_id: UUID) -> User | None:
        return UserRepository(session).get_by_public_id(public_id)

    def list_users(self, session: Session) -> list[UserRead]:
        users = UserRepository(session).list()
        role_repo = UserRoleRepository(session)
        result = []
        for user in users:
            role_names = role_repo.get_role_names_for_user(user.id)
            result.append(
                UserRead.model_validate(user).model_copy(update={"roles": role_names})
            )
        return result

    def update_user(
        self,
        session: Session,
        public_id: UUID,
        **kwargs,
    ) -> User | None:
        repo = UserRepository(session)
        user = repo.get_by_public_id(public_id)
        if user is None:
            return None
        return repo.update(user, UserUpdate(**kwargs))

    def change_password(
        self,
        session: Session,
        public_id: UUID,
        new_password: str,
        current_user_public_id: UUID,
    ) -> User:
        repo = UserRepository(session)
        user = repo.get_by_public_id(public_id)
        if user is None:
            raise LookupError("User not found")
        if user.public_id != current_user_public_id:
            raise PermissionError("Cannot change another user's password")
        updated = repo.update(user, UserUpdate(password_hash=hash_password(new_password)))
        RefreshTokenService().revoke_all_for_user(session, user.id)
        return updated

    def import_from_csv(
        self,
        session: Session,
        csv_bytes: bytes,
        school_public_id: str,
        course_public_id: str,
        requesting_user_id: int,
    ) -> dict:
        import csv
        import io
        from sqlmodel import select

        from app.domains.academic.models.lms_course import LmsCourse
        from app.domains.academic.models.school import School
        from app.domains.academic.repositories.course_student_repository import (
            CourseStudentRepository,
        )
        from app.domains.academic.services.academic_service import AcademicService
        from app.domains.rbac.models.role import Role
        from app.domains.rbac.models.user_role import UserRole

        try:
            school_uuid = UUID(school_public_id)
            course_uuid = UUID(course_public_id)
        except (ValueError, TypeError):
            raise ValueError("school_id o course_id inválido")

        school = session.exec(
            select(School).where(School.public_id == school_uuid)
        ).first()
        if not school:
            raise LookupError("Colegio no encontrado")

        course = session.exec(
            select(LmsCourse).where(
                LmsCourse.public_id == course_uuid,
                LmsCourse.is_active == True,  # noqa: E712
            )
        ).first()
        if not course:
            raise LookupError("Curso no encontrado")

        if course.school_id != school.id:
            raise ValueError("El curso no pertenece a ese colegio")

        student_role = session.exec(
            select(Role).where(Role.name == "STUDENT")
        ).first()

        user_repo = UserRepository(session)
        course_student_repo = CourseStudentRepository(session)
        academic_svc = AcademicService()

        try:
            content = csv_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                content = csv_bytes.decode("cp1252")
            except UnicodeDecodeError:
                raise ValueError(
                    "No se pudo decodificar el archivo. "
                    "Guárdalo como UTF-8 o como CSV de Excel."
                )
        first_line = content.split("\n")[0]
        delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
        try:
            reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
        except Exception:
            raise ValueError("El archivo no es un CSV válido")

        required = {"nombre", "apellido", "email", "password"}
        headers = set(reader.fieldnames or [])
        missing = required - headers
        if missing:
            raise ValueError(f"Faltan columnas: {', '.join(missing)}")

        results: dict = {"created": [], "errors": []}

        for i, row in enumerate(reader, start=2):
            email = row.get("email", "").strip().lower()
            nombre = row.get("nombre", "").strip()
            apellido = row.get("apellido", "").strip()
            password = row.get("password", "").strip()
            telefono = row.get("telefono", "").strip() or None

            if not email:
                results["errors"].append(
                    {"row": i, "email": "-", "error": "Email vacío"}
                )
                continue

            if not nombre or not apellido:
                results["errors"].append(
                    {"row": i, "email": email, "error": "Nombre o apellido vacío"}
                )
                continue

            if len(password) < 8:
                results["errors"].append(
                    {
                        "row": i,
                        "email": email,
                        "error": "Password debe tener mínimo 8 caracteres",
                    }
                )
                continue

            if user_repo.get_by_email(email):
                results["errors"].append(
                    {"row": i, "email": email, "error": "Email ya existe en el sistema"}
                )
                continue

            try:
                new_user = user_repo.create(
                    UserCreate(
                        email=email,
                        password_hash=hash_password(password),
                        first_name=nombre,
                        last_name=apellido,
                        phone=telefono,
                        position=None,
                        is_active=True,
                    )
                )

                if student_role:
                    session.add(
                        UserRole(user_id=new_user.id, role_id=student_role.id)
                    )
                    session.commit()

                academic_svc.add_member_to_school(
                    session, school.id, new_user.id, requesting_user_id
                )

                course_student_repo.enroll(course.id, new_user.id)

                results["created"].append(email)
            except Exception as exc:
                session.rollback()
                results["errors"].append(
                    {"row": i, "email": email, "error": str(exc)}
                )

        results["total"] = len(results["created"]) + len(results["errors"])
        results["success_count"] = len(results["created"])
        results["error_count"] = len(results["errors"])
        return results
