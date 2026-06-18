"""Pruebas del importador CSV idempotente de estudiantes (Reinicio de Ciclo LMS).

Cubre los casos del Sprint 3: grupo OK, grupo mal escrito (todo-o-nada con
sugerencia), email nuevo, email existente (reutilizado, no duplicado) y email
duplicado dentro del CSV. Más normalización de grupo e idempotencia al reimportar.

El servicio se ejercita directamente contra la sesión en memoria — no toca la
capa HTTP. Ver `app/domains/auth/services/user_service.py::import_from_csv`.
"""
import pytest
from sqlmodel import select

from app.core.security import hash_password
from app.domains.auth.models import User
from app.domains.auth.schemas import UserCreate
from app.domains.auth.services.user_service import UserService, _normalize_group
from app.domains.rbac.models import Role, UserRole

# Importar los modelos academic/audit usados por el importador para que
# SQLModel.metadata cree sus tablas antes de create_all (fixture `engine`).
from app.domains.academic.models.school import School, WorkLine  # noqa: F401
from app.domains.academic.models.lms_grade import LmsGrade  # noqa: F401
from app.domains.academic.models.lms_course import LmsCourse  # noqa: F401
from app.domains.academic.models.lms_course_student import LmsCourseStudent  # noqa: F401
from app.domains.academic.models.school_teacher import SchoolTeacher  # noqa: F401
from app.domains.audit.models import AuditLog  # noqa: F401


def _csv(*rows: str, header: str = "grupo;nombre;apellido;email") -> bytes:
    return ("\n".join([header, *rows])).encode("utf-8")


@pytest.fixture(name="school_setup")
def school_setup_fixture(session):
    """Colegio con 3 cursos (SEGUNDO, SEGUNDO B, TERCERO), un admin que solicita
    la importación, un docente para los cursos y los roles ADMIN/STUDENT/TEACHER.
    """
    admin = User(
        email="admin@rs.com", password_hash=hash_password("x"),
        first_name="Ada", last_name="Admin",
    )
    teacher = User(
        email="teacher@rs.com", password_hash=hash_password("x"),
        first_name="Tomas", last_name="Profe",
    )
    session.add(admin)
    session.add(teacher)
    session.commit()
    session.refresh(admin)
    session.refresh(teacher)

    roles = {
        name: Role(name=name) for name in ("ADMIN", "STUDENT", "TEACHER")
    }
    session.add_all(roles.values())
    session.commit()
    for r in roles.values():
        session.refresh(r)

    session.add(UserRole(user_id=admin.id, role_id=roles["ADMIN"].id))
    session.add(UserRole(user_id=teacher.id, role_id=roles["TEACHER"].id))
    session.commit()

    school = School(name="Colegio RobotSchool", work_line=WorkLine.robotschool)
    session.add(school)
    session.commit()
    session.refresh(school)

    grade = LmsGrade(school_id=school.id, name="Grado")
    session.add(grade)
    session.commit()
    session.refresh(grade)

    for cname in ("SEGUNDO", "SEGUNDO B", "TERCERO"):
        session.add(
            LmsCourse(
                school_id=school.id, grade_id=grade.id,
                name=cname, teacher_id=teacher.id,
            )
        )
    session.commit()

    return {"school": school, "admin": admin, "grade": grade}


def _run(session, setup, csv_bytes):
    return UserService().import_from_csv(
        session,
        csv_bytes,
        school_public_id=str(setup["school"].public_id),
        requesting_user_id=setup["admin"].id,
    )


def _student_emails(session) -> set[str]:
    """Emails de usuarios con rol STUDENT en la BD."""
    rows = session.exec(
        select(User.email)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.name == "STUDENT")
    ).all()
    return set(rows)


# ── Normalización ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("segundo b", "SEGUNDO B"),
        ("  Segundo   B  ", "SEGUNDO B"),
        ("SÉPTIMO", "SEPTIMO"),
        ("Tercéro", "TERCERO"),
        ("", ""),
    ],
)
def test_normalize_group(raw, expected):
    assert _normalize_group(raw) == expected


# ── Caso 1 + 3: grupos válidos, emails nuevos ────────────────────────────────

def test_grupos_validos_crea_y_matricula(session, school_setup):
    result = _run(
        session, school_setup,
        _csv(
            "SEGUNDO;Ana;Pérez;ana@rs.com",
            "SEGUNDO B;Luis;Gómez;luis@rs.com",
            "TERCERO;Mara;Díaz;mara@rs.com",
        ),
    )
    assert result["aborted"] is False
    assert result["created_count"] == 3
    assert result["reused_count"] == 0
    assert result["enrolled_count"] == 3
    assert _student_emails(session) == {"ana@rs.com", "luis@rs.com", "mara@rs.com"}


# ── Normalización aplicada al matching de grupo ──────────────────────────────

def test_matching_normaliza_tildes_y_espacios(session, school_setup):
    result = _run(
        session, school_setup,
        _csv("  segundo   b ;Ana;Pérez;ana@rs.com"),  # casa con "SEGUNDO B"
    )
    assert result["aborted"] is False
    assert result["enrolled_count"] == 1


# ── Caso 4: email existente se reutiliza, no se duplica ───────────────────────

def test_email_existente_se_reutiliza(session, school_setup):
    existing = UserService().register(
        session, email="ana@rs.com", password="secret123",
        first_name="Ana", last_name="Vieja",
    )
    result = _run(session, school_setup, _csv("SEGUNDO;Ana;Pérez;ana@rs.com"))
    assert result["aborted"] is False
    assert result["created_count"] == 0
    assert result["reused_count"] == 1
    assert result["enrolled_count"] == 1
    # No se creó un segundo usuario con ese email.
    same = session.exec(select(User).where(User.email == "ana@rs.com")).all()
    assert len(same) == 1
    assert same[0].id == existing.id


# ── Idempotencia: reimportar el mismo CSV no duplica ─────────────────────────

def test_reimportar_es_idempotente(session, school_setup):
    csv = _csv(
        "SEGUNDO;Ana;Pérez;ana@rs.com",
        "TERCERO;Mara;Díaz;mara@rs.com",
    )
    first = _run(session, school_setup, csv)
    assert first["created_count"] == 2

    second = _run(session, school_setup, csv)
    assert second["aborted"] is False
    assert second["created_count"] == 0
    assert second["reused_count"] == 2
    assert second["enrolled_count"] == 2

    # Siguen siendo exactamente 2 estudiantes y 2 matrículas activas.
    assert len(_student_emails(session)) == 2
    active = session.exec(
        select(LmsCourseStudent).where(LmsCourseStudent.is_active == True)  # noqa: E712
    ).all()
    assert len(active) == 2


# ── Caso 2: grupo mal escrito → aborta, no escribe nada, sugiere ─────────────

def test_grupo_mal_escrito_aborta_con_sugerencia(session, school_setup):
    result = _run(
        session, school_setup,
        _csv(
            "SEGUNDO;Ana;Pérez;ana@rs.com",       # válida
            "SEGUNDOO B;Luis;Gómez;luis@rs.com",  # typo → no existe
        ),
    )
    assert result["aborted"] is True
    assert result["created_count"] == 0
    assert result["enrolled_count"] == 0
    assert result["error_count"] == 1
    err = result["errors"][0]
    assert err["row"] == 3
    assert "SEGUNDO B" in err["error"]  # sugerencia por difflib
    # Todo-o-nada: ni siquiera la fila válida se escribió.
    assert _student_emails(session) == set()


# ── Caso 5: email duplicado dentro del CSV → aborta ──────────────────────────

def test_email_duplicado_en_csv_aborta(session, school_setup):
    result = _run(
        session, school_setup,
        _csv(
            "SEGUNDO;Ana;Pérez;ana@rs.com",
            "TERCERO;Otra;Ana;ana@rs.com",  # email repetido
        ),
    )
    assert result["aborted"] is True
    assert result["error_count"] == 1
    assert "duplicado" in result["errors"][0]["error"].lower()
    assert _student_emails(session) == set()


# ── Filas incompletas / email inválido también abortan ───────────────────────

def test_fila_incompleta_aborta(session, school_setup):
    result = _run(
        session, school_setup,
        _csv("SEGUNDO;Ana;;ana@rs.com"),  # apellido vacío
    )
    assert result["aborted"] is True
    assert "incompleta" in result["errors"][0]["error"].lower()
    assert _student_emails(session) == set()


def test_email_invalido_aborta(session, school_setup):
    result = _run(
        session, school_setup,
        _csv("SEGUNDO;Ana;Pérez;ana-sin-arroba"),
    )
    assert result["aborted"] is True
    assert "inválido" in result["errors"][0]["error"].lower()
    assert _student_emails(session) == set()
