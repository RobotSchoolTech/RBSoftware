"""Multi-docente por curso: membresía, permisos y visibilidad.

Cubre los 5 casos exigidos por el spec §2.9 más los dos bloqueantes que la
review del PR #12 levantó: el detalle del curso no validaba autorización, y un
DIRECTOR co-asignado a un curso de otro grado no lo veía en /my-courses.
"""
import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.domains.academic.models.lms_course import LmsCourse
from app.domains.academic.models.lms_course_student import LmsCourseStudent
from app.domains.academic.models.lms_course_teacher import LmsCourseTeacher
from app.domains.academic.models.lms_grade import LmsGrade
from app.domains.academic.models.lms_grade_director import LmsGradeDirector
from app.domains.academic.models.school import School
from app.domains.auth.models import User
from app.domains.rbac.models import Role, UserRole


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_user(session, email: str, first: str = "Test") -> User:
    user = User(
        email=email,
        password_hash=hash_password("secret123"),
        first_name=first,
        last_name="User",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _grant_role(session, user: User, role_name: str) -> None:
    role = session.query(Role).filter(Role.name == role_name).first()
    if role is None:
        role = Role(name=role_name, description=role_name)
        session.add(role)
        session.commit()
        session.refresh(role)
    session.add(UserRole(user_id=user.id, role_id=role.id))
    session.commit()


def _login(client: TestClient, email: str) -> None:
    response = client.post(
        "/auth/login", json={"email": email, "password": "secret123"}
    )
    assert response.status_code == 200, response.text


@pytest.fixture(name="world")
def world_fixture(session):
    """Un colegio, dos grados (6A y 7A) y un curso en cada uno.

    El curso de 6A arranca con `teacher_a` como único docente, replicando el
    estado que deja la migración: toda fila de `lms_courses.teacher_id` tiene su
    par en `lms_course_teachers`.
    """
    school = School(name="Colegio Test", city="Cali")
    session.add(school)
    session.commit()
    session.refresh(school)

    grade_6a = LmsGrade(school_id=school.id, name="6A")
    grade_7a = LmsGrade(school_id=school.id, name="7A")
    session.add(grade_6a)
    session.add(grade_7a)
    session.commit()
    session.refresh(grade_6a)
    session.refresh(grade_7a)

    teacher_a = _make_user(session, "docente.a@robotschool.com", "Ana")
    teacher_b = _make_user(session, "docente.b@robotschool.com", "Beto")
    _grant_role(session, teacher_a, "TEACHER")
    _grant_role(session, teacher_b, "TEACHER")

    course_6a = LmsCourse(
        grade_id=grade_6a.id,
        school_id=school.id,
        name="Robótica 6A",
        teacher_id=teacher_a.id,
    )
    course_7a = LmsCourse(
        grade_id=grade_7a.id,
        school_id=school.id,
        name="Robótica 7A",
        teacher_id=teacher_a.id,
    )
    session.add(course_6a)
    session.add(course_7a)
    session.commit()
    session.refresh(course_6a)
    session.refresh(course_7a)

    session.add(LmsCourseTeacher(course_id=course_6a.id, user_id=teacher_a.id))
    session.add(LmsCourseTeacher(course_id=course_7a.id, user_id=teacher_a.id))
    session.commit()

    return {
        "school": school,
        "grade_6a": grade_6a,
        "grade_7a": grade_7a,
        "course_6a": course_6a,
        "course_7a": course_7a,
        "teacher_a": teacher_a,
        "teacher_b": teacher_b,
    }


@pytest.fixture(name="admin_client")
def admin_client_fixture(client: TestClient, session):
    admin = _make_user(session, "admin@robotschool.com", "Admin")
    _grant_role(session, admin, "ADMIN")
    _login(client, "admin@robotschool.com")
    return client, admin


# ── §2.9.1 — idempotencia ─────────────────────────────────────────────────────


def test_add_teacher_is_idempotent(admin_client, world, session) -> None:
    """Agregar dos veces al mismo docente deja UNA fila, no dos."""
    client, _ = admin_client
    course = world["course_6a"]
    teacher_b = world["teacher_b"]

    for _ in range(2):
        response = client.post(
            f"/academic/courses/{course.public_id}/teachers",
            json={"teacher_id": str(teacher_b.public_id)},
        )
        assert response.status_code == 204, response.text

    rows = (
        session.query(LmsCourseTeacher)
        .filter(
            LmsCourseTeacher.course_id == course.id,
            LmsCourseTeacher.user_id == teacher_b.id,
        )
        .all()
    )
    assert len(rows) == 1


# ── §2.9.2 — el co-docente tiene acceso real ──────────────────────────────────


def test_second_teacher_gets_access(client: TestClient, world, session) -> None:
    """Un segundo docente agregado ve el curso y su contenido."""
    course = world["course_6a"]
    teacher_b = world["teacher_b"]

    _login(client, "docente.b@robotschool.com")
    before = client.get(f"/academic/courses/{course.public_id}")
    assert before.status_code == 403

    session.add(LmsCourseTeacher(course_id=course.id, user_id=teacher_b.id))
    session.commit()

    after = client.get(f"/academic/courses/{course.public_id}")
    assert after.status_code == 200
    emails = {t["email"] for t in after.json()["teachers"]}
    assert emails == {"docente.a@robotschool.com", "docente.b@robotschool.com"}

    content = client.get(f"/academic/courses/{course.public_id}/content")
    assert content.status_code == 200


# ── §2.9.3 — quitar a un docente le quita el acceso ───────────────────────────


def test_removed_teacher_loses_access(admin_client, client, world, session) -> None:
    """El docente removido pierde el acceso en el request siguiente."""
    course = world["course_6a"]
    teacher_b = world["teacher_b"]
    session.add(LmsCourseTeacher(course_id=course.id, user_id=teacher_b.id))
    session.commit()

    admin, _ = admin_client
    removed = admin.delete(
        f"/academic/courses/{course.public_id}/teachers/{teacher_b.public_id}"
    )
    assert removed.status_code == 204, removed.text

    _login(client, "docente.b@robotschool.com")
    assert client.get(f"/academic/courses/{course.public_id}").status_code == 403


# ── §2.9.4 — no se puede dejar el curso sin docentes ──────────────────────────


def test_cannot_remove_last_teacher(admin_client, world, session) -> None:
    """Quitar al único docente devuelve 400 y no deja el curso huérfano."""
    client, _ = admin_client
    course = world["course_6a"]
    teacher_a = world["teacher_a"]

    response = client.delete(
        f"/academic/courses/{course.public_id}/teachers/{teacher_a.public_id}"
    )
    assert response.status_code == 400
    assert "último docente" in response.json()["detail"]

    rows = (
        session.query(LmsCourseTeacher)
        .filter(LmsCourseTeacher.course_id == course.id)
        .all()
    )
    assert len(rows) == 1


def test_remove_non_teacher_returns_404(admin_client, world) -> None:
    client, _ = admin_client
    course = world["course_6a"]
    teacher_b = world["teacher_b"]

    response = client.delete(
        f"/academic/courses/{course.public_id}/teachers/{teacher_b.public_id}"
    )
    assert response.status_code == 404


# ── §2.9.5 — la membresía es ADMIN-only ───────────────────────────────────────


@pytest.mark.parametrize(
    "email,role",
    [("director@robotschool.com", "DIRECTOR"), ("profe@robotschool.com", "TEACHER")],
)
def test_add_and_remove_teacher_are_admin_only(
    client: TestClient, session, world, email, role
) -> None:
    """DIRECTOR y TEACHER reciben 403 en POST y DELETE de docentes."""
    course = world["course_6a"]
    teacher_a = world["teacher_a"]
    teacher_b = world["teacher_b"]

    actor = _make_user(session, email, role.title())
    _grant_role(session, actor, role)
    # Aun siendo director del grado del curso, no puede tocar la membresía.
    session.add(LmsGradeDirector(grade_id=course.grade_id, user_id=actor.id))
    session.commit()

    _login(client, email)

    added = client.post(
        f"/academic/courses/{course.public_id}/teachers",
        json={"teacher_id": str(teacher_b.public_id)},
    )
    assert added.status_code == 403

    removed = client.delete(
        f"/academic/courses/{course.public_id}/teachers/{teacher_a.public_id}"
    )
    assert removed.status_code == 403


# ── Bloqueante 1 — GET /courses/{id} valida autorización ──────────────────────


def test_course_detail_denies_unrelated_user(client: TestClient, session, world) -> None:
    """Un usuario autenticado sin vínculo con el curso NO obtiene el roster.

    Era broken access control: cualquiera con un public_id sacaba la lista
    completa de estudiantes (menores de edad).
    """
    _make_user(session, "ajeno@robotschool.com", "Ajeno")
    _login(client, "ajeno@robotschool.com")

    response = client.get(f"/academic/courses/{world['course_6a'].public_id}")
    assert response.status_code == 403


def test_course_detail_hides_roster_from_students(
    client: TestClient, session, world
) -> None:
    """El estudiante matriculado ve el curso y sus docentes, no a sus compañeros."""
    course = world["course_6a"]
    student = _make_user(session, "estudiante@robotschool.com", "Estu")
    classmate = _make_user(session, "companero@robotschool.com", "Compa")
    session.add(LmsCourseStudent(course_id=course.id, user_id=student.id))
    session.add(LmsCourseStudent(course_id=course.id, user_id=classmate.id))
    session.commit()

    _login(client, "estudiante@robotschool.com")
    response = client.get(f"/academic/courses/{course.public_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["students"] == []
    assert len(body["teachers"]) == 1


def test_course_detail_gives_roster_to_teacher(client: TestClient, session, world) -> None:
    course = world["course_6a"]
    student = _make_user(session, "estudiante@robotschool.com", "Estu")
    session.add(LmsCourseStudent(course_id=course.id, user_id=student.id))
    session.commit()

    _login(client, "docente.a@robotschool.com")
    response = client.get(f"/academic/courses/{course.public_id}")

    assert response.status_code == 200
    assert len(response.json()["students"]) == 1


# ── Bloqueante 2 — un DIRECTOR co-docente ve el curso en /my-courses ──────────


def test_director_sees_courses_where_is_cotecher(
    client: TestClient, session, world
) -> None:
    """Director de 6A co-asignado a un curso de 7A: debe ver AMBOS cursos.

    Antes `get_my_courses_as_teacher` hacía un return temprano con los cursos
    del grado dirigido y nunca unía los cursos donde la persona dicta. El
    director tenía permiso de entrar por URL directa pero no forma de llegar.
    """
    director = _make_user(session, "director@robotschool.com", "Jose")
    _grant_role(session, director, "DIRECTOR")
    session.add(
        LmsGradeDirector(grade_id=world["grade_6a"].id, user_id=director.id)
    )
    session.add(
        LmsCourseTeacher(course_id=world["course_7a"].id, user_id=director.id)
    )
    session.commit()

    _login(client, "director@robotschool.com")
    response = client.get("/academic/my-courses")

    assert response.status_code == 200
    names = {c["name"] for c in response.json()}
    assert names == {"Robótica 6A", "Robótica 7A"}


def test_my_courses_does_not_duplicate(client: TestClient, session, world) -> None:
    """Director de 6A que además dicta en 6A ve el curso UNA vez, no dos."""
    director = _make_user(session, "director@robotschool.com", "Jose")
    _grant_role(session, director, "DIRECTOR")
    session.add(
        LmsGradeDirector(grade_id=world["grade_6a"].id, user_id=director.id)
    )
    session.add(
        LmsCourseTeacher(course_id=world["course_6a"].id, user_id=director.id)
    )
    session.commit()

    _login(client, "director@robotschool.com")
    response = client.get("/academic/my-courses")

    assert response.status_code == 200
    names = [c["name"] for c in response.json()]
    assert names.count("Robótica 6A") == 1
