#!/usr/bin/env python3
"""
Seed de datos para pruebas.
Idempotente: no falla ni duplica si los datos ya existen.

Uso dentro del contenedor:
    python scripts/seed.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone
from sqlmodel import Session, create_engine, select

from app.core.config import settings
from app.domains.auth.models import User
from app.domains.auth.services.user_service import UserService
from app.domains.inventory.models.stock_location import LocationType, StockLocation
from app.domains.inventory.schemas.location import LocationCreate
from app.domains.inventory.services.inventory_service import InventoryService
from app.domains.rbac.models import Role, UserRole
from app.domains.rbac.repositories import RoleRepository, UserRoleRepository
from app.domains.rbac.schemas import RoleCreate, UserRoleCreate

engine = create_engine(settings.database_url)


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_or_create_user(session: Session, svc: UserService, **kwargs) -> User:
    existing = session.exec(select(User).where(User.email == kwargs["email"])).first()
    if existing:
        print(f"  [skip] usuario '{kwargs['email']}' ya existe")
        return existing
    user = svc.register(session, **kwargs)
    print(f"  [ok]   usuario '{kwargs['email']}' creado")
    return user


# ── Usuarios ──────────────────────────────────────────────────────────────────

USERS = [
    dict(email="admin@robotschool.com",        password="Admin1234!",        first_name="Admin",    last_name="RobotSchool",   position="Administrador"),
    dict(email="supertrainer@robotschool.com", password="SuperTrainer1234!", first_name="Ana",      last_name="Supervisora",   position="Coordinadora de Capacitación"),
    dict(email="trainer@robotschool.com",      password="Trainer1234!",      first_name="Carlos",   last_name="Instructor",    position="Instructor de Robótica"),
    dict(email="trainer2@robotschool.com",     password="Trainer1234!",      first_name="Laura",    last_name="Formadora",     position="Instructora de Programación"),
    dict(email="trainer3@robotschool.com",     password="Trainer1234!",      first_name="Miguel",   last_name="Capacitador",   position="Instructor FLL"),
    # Directores
    dict(email="director4@sanpedro.edu.co",    password="Director1234!",     first_name="Carlos",   last_name="Ruiz",          position="Director de Grado"),
    dict(email="director1@lasalle.edu.co",     password="Director1234!",     first_name="Patricia", last_name="Mendoza",       position="Directora de Grado"),
    dict(email="director2@lasalle.edu.co",     password="Director1234!",     first_name="Roberto",  last_name="Vargas",        position="Director de Grado"),
    dict(email="director1@losandes.edu.co",    password="Director1234!",     first_name="Sofía",    last_name="Castro",        position="Directora de Grado"),
    # Docentes
    dict(email="docente1@sanpedro.edu.co",     password="Docente1234!",      first_name="María",    last_name="García",        position="Docente"),
    dict(email="docente2@sanpedro.edu.co",     password="Docente1234!",      first_name="Pedro",    last_name="Morales",       position="Docente"),
    dict(email="docente1@lasalle.edu.co",      password="Docente1234!",      first_name="Claudia",  last_name="Torres",        position="Docente"),
    dict(email="docente2@lasalle.edu.co",      password="Docente1234!",      first_name="Andrés",   last_name="Herrera",       position="Docente"),
    dict(email="docente1@losandes.edu.co",     password="Docente1234!",      first_name="Valentina",last_name="Ríos",          position="Docente"),
    dict(email="docente2@losandes.edu.co",     password="Docente1234!",      first_name="Felipe",   last_name="Sánchez",       position="Docente"),
    # Estudiantes
    dict(email="estudiante1@sanpedro.edu.co",  password="Estudiante1234!",   first_name="Juan",     last_name="Pérez"),
    dict(email="estudiante2@sanpedro.edu.co",  password="Estudiante1234!",   first_name="Ana",      last_name="López"),
    dict(email="estudiante3@sanpedro.edu.co",  password="Estudiante1234!",   first_name="Luis",     last_name="Gómez"),
    dict(email="estudiante4@sanpedro.edu.co",  password="Estudiante1234!",   first_name="Sara",     last_name="Díaz"),
    dict(email="estudiante1@lasalle.edu.co",   password="Estudiante1234!",   first_name="Diego",    last_name="Martínez"),
    dict(email="estudiante2@lasalle.edu.co",   password="Estudiante1234!",   first_name="Camila",   last_name="Jiménez"),
    dict(email="estudiante1@losandes.edu.co",  password="Estudiante1234!",   first_name="Sebastián",last_name="Rojas"),
    dict(email="estudiante2@losandes.edu.co",  password="Estudiante1234!",   first_name="Isabella", last_name="Flores"),
]

USER_ROLE_ASSIGNMENTS = [
    ("admin@robotschool.com",        "ADMIN"),
    ("supertrainer@robotschool.com", "SUPER_TRAINER"),
    ("trainer@robotschool.com",      "TRAINER"),
    ("trainer2@robotschool.com",     "TRAINER"),
    ("trainer3@robotschool.com",     "TRAINER"),
    ("director4@sanpedro.edu.co",    "DIRECTOR"),
    ("director1@lasalle.edu.co",     "DIRECTOR"),
    ("director2@lasalle.edu.co",     "DIRECTOR"),
    ("director1@losandes.edu.co",    "DIRECTOR"),
    ("docente1@sanpedro.edu.co",     "TEACHER"),
    ("docente2@sanpedro.edu.co",     "TEACHER"),
    ("docente1@lasalle.edu.co",      "TEACHER"),
    ("docente2@lasalle.edu.co",      "TEACHER"),
    ("docente1@losandes.edu.co",     "TEACHER"),
    ("docente2@losandes.edu.co",     "TEACHER"),
    ("estudiante1@sanpedro.edu.co",  "STUDENT"),
    ("estudiante2@sanpedro.edu.co",  "STUDENT"),
    ("estudiante3@sanpedro.edu.co",  "STUDENT"),
    ("estudiante4@sanpedro.edu.co",  "STUDENT"),
    ("estudiante1@lasalle.edu.co",   "STUDENT"),
    ("estudiante2@lasalle.edu.co",   "STUDENT"),
    ("estudiante1@losandes.edu.co",  "STUDENT"),
    ("estudiante2@losandes.edu.co",  "STUDENT"),
]


def seed_users(session: Session) -> None:
    svc = UserService()
    for u in USERS:
        get_or_create_user(session, svc, **u)


def seed_roles(session: Session) -> None:
    roles = [
        RoleCreate(name="ADMIN",        description="Acceso total al sistema"),
        RoleCreate(name="DIRECTOR",     description="Director de grado en colegio"),
        RoleCreate(name="TEACHER",      description="Docente de curso"),
        RoleCreate(name="STUDENT",      description="Estudiante matriculado"),
        RoleCreate(name="OPERATIVO",    description="Personal de producción y bodega"),
        RoleCreate(name="COMERCIAL",    description="Personal de ventas y órdenes"),
        RoleCreate(name="TRAINER",      description="Instructor de capacitación docente de RobotSchool"),
        RoleCreate(name="SUPER_TRAINER",description="Instructor jefe. Puede ver y gestionar todos los programas y asignar TRAINERs."),
    ]
    repo = RoleRepository(session)
    for role_data in roles:
        if repo.get_by_name(role_data.name):
            print(f"  [skip] rol '{role_data.name}' ya existe")
        else:
            repo.create(role_data)
            print(f"  [ok]   rol '{role_data.name}' creado")


def seed_user_roles(session: Session) -> None:
    role_repo = RoleRepository(session)
    ur_repo = UserRoleRepository(session)
    for email, role_name in USER_ROLE_ASSIGNMENTS:
        user = session.exec(select(User).where(User.email == email)).first()
        if user is None:
            print(f"  [warn] usuario '{email}' no existe, saltando")
            continue
        role = role_repo.get_by_name(role_name)
        if role is None:
            print(f"  [warn] rol '{role_name}' no existe, saltando")
            continue
        existing = [ur for ur in ur_repo.list_by_user_id(user.id) if ur.role_id == role.id]
        if existing:
            print(f"  [skip] '{email}' ya tiene rol '{role_name}'")
            continue
        ur_repo.create(UserRoleCreate(user_id=user.id, role_id=role.id))
        print(f"  [ok]   '{email}' → '{role_name}'")


# ── Ubicaciones ───────────────────────────────────────────────────────────────

def seed_locations(session: Session) -> None:
    locations = [
        LocationCreate(name="Bodega Principal", type=LocationType.WAREHOUSE),
        LocationCreate(name="Sede Bogotá",       type=LocationType.SEDE),
        LocationCreate(name="Sede 2",            type=LocationType.SEDE),
        LocationCreate(name="Sede 3",            type=LocationType.SEDE),
    ]
    svc = InventoryService()
    for loc in locations:
        existing = session.exec(select(StockLocation).where(StockLocation.name == loc.name)).first()
        if existing:
            print(f"  [skip] ubicación '{loc.name}' ya existe")
        else:
            svc.create_location(session, loc)
            print(f"  [ok]   ubicación '{loc.name}' creada")


# ── Académico ─────────────────────────────────────────────────────────────────

def seed_academic(session: Session) -> None:
    from app.domains.academic.models.school import School
    from app.domains.academic.models.lms_grade import LmsGrade
    from app.domains.academic.models.lms_course import LmsCourse
    from app.domains.academic.models.lms_unit import LmsUnit
    from app.domains.academic.models.lms_material import LmsMaterial
    from app.domains.academic.models.lms_assignment import LmsAssignment
    from app.domains.academic.repositories import (
        SchoolRepository, GradeRepository, CourseRepository,
        CourseStudentRepository, GradeDirectorRepository,
        UnitRepository, MaterialRepository, AssignmentRepository,
    )
    from app.domains.academic.schemas import (
        SchoolCreate, GradeCreate, CourseCreate,
        UnitCreate, MaterialCreate, AssignmentCreate,
    )

    def get_or_create_school(name: str, city: str) -> School:
        s = session.exec(select(School).where(School.name == name)).first()
        if s:
            print(f"  [skip] colegio '{name}' ya existe")
            return s
        s = SchoolRepository(session).create(SchoolCreate(name=name, city=city))
        print(f"  [ok]   colegio '{name}' creado")
        return s

    def get_or_create_grade(school: School, name: str) -> LmsGrade:
        g = session.exec(select(LmsGrade).where(LmsGrade.name == name, LmsGrade.school_id == school.id)).first()
        if g:
            print(f"  [skip] grado '{name}' ya existe")
            return g
        g = GradeRepository(session).create(school.id, GradeCreate(name=name))
        print(f"  [ok]   grado '{name}' creado en '{school.name}'")
        return g

    def get_or_create_course(grade: LmsGrade, school: School, teacher: User, name: str) -> LmsCourse:
        c = session.exec(select(LmsCourse).where(LmsCourse.name == name, LmsCourse.grade_id == grade.id)).first()
        if c:
            print(f"  [skip] curso '{name}' ya existe")
            return c
        c = CourseRepository(session).create(grade.id, school.id, teacher.id, CourseCreate(name=name))
        print(f"  [ok]   curso '{name}' creado")
        return c

    def assign_director(grade: LmsGrade, director: User) -> None:
        repo = GradeDirectorRepository(session)
        if repo.is_director_of_grade(grade.id, director.id):
            print(f"  [skip] director '{director.email}' ya asignado")
        else:
            repo.assign(grade.id, director.id)
            print(f"  [ok]   director '{director.email}' → '{grade.name}'")

    def enroll_student(course: LmsCourse, student: User) -> None:
        repo = CourseStudentRepository(session)
        if repo.is_enrolled(course.id, student.id):
            print(f"  [skip] '{student.email}' ya enrolled")
        else:
            repo.enroll(course.id, student.id)
            print(f"  [ok]   '{student.email}' enrolled en '{course.name}'")

    def add_unit_with_content(course: LmsCourse, title: str, order: int) -> LmsUnit:
        u = session.exec(select(LmsUnit).where(LmsUnit.title == title, LmsUnit.course_id == course.id)).first()
        if u:
            print(f"  [skip] unidad '{title}' ya existe")
            return u
        u = UnitRepository(session).create(course.id, UnitCreate(title=title, order_index=order))
        u.is_published = True
        session.add(u)
        session.commit()
        session.refresh(u)
        print(f"  [ok]   unidad '{title}' creada")

        mat = session.exec(select(LmsMaterial).where(LmsMaterial.title == f"Material: {title}", LmsMaterial.unit_id == u.id)).first()
        if not mat:
            MaterialRepository(session).create(u.id, MaterialCreate(
                title=f"Material: {title}",
                type="TEXT",
                content=f"Contenido de la unidad '{title}'. Aquí van los materiales de estudio.",
                is_published=True,
            ))
            print(f"  [ok]   material de '{title}' creado")

        assign = session.exec(select(LmsAssignment).where(LmsAssignment.title == f"Tarea: {title}", LmsAssignment.unit_id == u.id)).first()
        if not assign:
            a = AssignmentRepository(session).create(u.id, AssignmentCreate(
                title=f"Tarea: {title}",
                description=f"Actividad práctica sobre '{title}'.",
                max_score=100,
            ))
            a.is_published = True
            session.add(a)
            session.commit()
            print(f"  [ok]   tarea de '{title}' creada")
        return u

    def get_user(email: str) -> User:
        return session.exec(select(User).where(User.email == email)).first()

    def assign_teacher_to_school(teacher_email: str, school: School) -> None:
        from app.domains.academic.models.school_teacher import SchoolTeacher
        user = get_user(teacher_email)
        if not user:
            return
        exists = session.exec(
            select(SchoolTeacher).where(
                SchoolTeacher.user_id == user.id,
                SchoolTeacher.school_id == school.id,
            )
        ).first()
        if exists:
            print(f"  [skip] '{teacher_email}' ya asignado a '{school.name}'")
            return
        session.add(SchoolTeacher(user_id=user.id, school_id=school.id))
        session.commit()
        print(f"  [seed] {teacher_email} → {school.name}")

    # ── Colegio San Pedro ──
    sp = get_or_create_school("Colegio San Pedro", "Bogotá")
    sp_g1 = get_or_create_grade(sp, "4to Primaria")
    sp_g2 = get_or_create_grade(sp, "5to Primaria")
    assign_director(sp_g1, get_user("director4@sanpedro.edu.co"))
    assign_director(sp_g2, get_user("director4@sanpedro.edu.co"))
    sp_c1 = get_or_create_course(sp_g1, sp, get_user("docente1@sanpedro.edu.co"), "4to A")
    sp_c2 = get_or_create_course(sp_g1, sp, get_user("docente2@sanpedro.edu.co"), "4to B")
    sp_c3 = get_or_create_course(sp_g2, sp, get_user("docente1@sanpedro.edu.co"), "5to A")
    for email in ["estudiante1@sanpedro.edu.co", "estudiante2@sanpedro.edu.co"]:
        enroll_student(sp_c1, get_user(email))
    for email in ["estudiante3@sanpedro.edu.co", "estudiante4@sanpedro.edu.co"]:
        enroll_student(sp_c2, get_user(email))
    add_unit_with_content(sp_c1, "Introducción a la Robótica", 0)
    add_unit_with_content(sp_c1, "Sensores y Actuadores", 1)
    add_unit_with_content(sp_c2, "Programación por Bloques", 0)
    add_unit_with_content(sp_c3, "Robótica Avanzada", 0)
    assign_teacher_to_school("docente1@sanpedro.edu.co", sp)
    assign_teacher_to_school("docente2@sanpedro.edu.co", sp)

    # ── Colegio La Salle ──
    ls = get_or_create_school("Colegio La Salle", "Medellín")
    ls_g1 = get_or_create_grade(ls, "3ro Primaria")
    ls_g2 = get_or_create_grade(ls, "4to Primaria")
    assign_director(ls_g1, get_user("director1@lasalle.edu.co"))
    assign_director(ls_g2, get_user("director2@lasalle.edu.co"))
    ls_c1 = get_or_create_course(ls_g1, ls, get_user("docente1@lasalle.edu.co"), "3ro A")
    ls_c2 = get_or_create_course(ls_g2, ls, get_user("docente2@lasalle.edu.co"), "4to A")
    for email in ["estudiante1@lasalle.edu.co", "estudiante2@lasalle.edu.co"]:
        enroll_student(ls_c1, get_user(email))
    add_unit_with_content(ls_c1, "Fundamentos de Tecnología", 0)
    add_unit_with_content(ls_c2, "Construcción con Lego", 0)
    assign_teacher_to_school("docente1@lasalle.edu.co", ls)
    assign_teacher_to_school("docente2@lasalle.edu.co", ls)

    # ── Colegio Los Andes ──
    la = get_or_create_school("Colegio Los Andes", "Cali")
    la_g1 = get_or_create_grade(la, "5to Primaria")
    assign_director(la_g1, get_user("director1@losandes.edu.co"))
    la_c1 = get_or_create_course(la_g1, la, get_user("docente1@losandes.edu.co"), "5to A")
    la_c2 = get_or_create_course(la_g1, la, get_user("docente2@losandes.edu.co"), "5to B")
    for email in ["estudiante1@losandes.edu.co", "estudiante2@losandes.edu.co"]:
        enroll_student(la_c1, get_user(email))
    add_unit_with_content(la_c1, "Pensamiento Computacional", 0)
    add_unit_with_content(la_c2, "Proyectos STEM", 0)
    assign_teacher_to_school("docente1@losandes.edu.co", la)
    assign_teacher_to_school("docente2@losandes.edu.co", la)


# ── Capacitación ─────────────────────────────────────────────────────────────

def seed_training(session: Session) -> None:
    from app.domains.training.models.training_program import TrainingProgram
    from app.domains.training.models.training_module import TrainingModule
    from app.domains.training.models.training_lesson import TrainingLesson
    from app.domains.training.models.training_evaluation import TrainingEvaluation
    from app.domains.training.models.training_quiz_question import TrainingQuizQuestion
    from app.domains.training.models.training_enrollment import TrainingEnrollment

    def get_user(email: str) -> User:
        return session.exec(select(User).where(User.email == email)).first()

    def get_or_create_program(name: str, description: str, objective: str, hours: int, trainer_email: str, is_active: bool = True) -> TrainingProgram:
        p = session.exec(select(TrainingProgram).where(TrainingProgram.name == name)).first()
        if p:
            print(f"  [skip] programa '{name}' ya existe")
            return p
        trainer = get_user(trainer_email)
        p = TrainingProgram(
            name=name, description=description, objective=objective,
            duration_hours=hours, is_active=is_active, is_published=is_active,
            created_by=trainer.id,
        )
        session.add(p)
        session.commit()
        session.refresh(p)
        print(f"  [ok]   programa '{name}' creado")
        return p

    def get_or_create_module(program: TrainingProgram, title: str, order: int) -> TrainingModule:
        m = session.exec(select(TrainingModule).where(TrainingModule.title == title, TrainingModule.program_id == program.id)).first()
        if m:
            print(f"  [skip] módulo '{title}' ya existe")
            return m
        m = TrainingModule(program_id=program.id, title=title, order_index=order, is_published=True)
        session.add(m)
        session.commit()
        session.refresh(m)
        print(f"  [ok]   módulo '{title}' creado")
        return m

    def get_or_create_lesson(module: TrainingModule, title: str, lesson_type: str, content: str, order: int) -> TrainingLesson:
        l = session.exec(select(TrainingLesson).where(TrainingLesson.title == title, TrainingLesson.module_id == module.id)).first()
        if l:
            print(f"  [skip] lección '{title}' ya existe")
            return l
        l = TrainingLesson(
            module_id=module.id, title=title, type=lesson_type,
            content=content, order_index=order, is_published=True,
            duration_minutes=15 if lesson_type == "TEXT" else 30,
        )
        session.add(l)
        session.commit()
        session.refresh(l)
        print(f"  [ok]   lección '{title}' creada")
        return l

    def get_or_create_evaluation(module: TrainingModule, title: str, eval_type: str, passing: int) -> TrainingEvaluation:
        e = session.exec(select(TrainingEvaluation).where(TrainingEvaluation.title == title, TrainingEvaluation.module_id == module.id)).first()
        if e:
            print(f"  [skip] evaluación '{title}' ya existe")
            return e
        e = TrainingEvaluation(module_id=module.id, title=title, type=eval_type, passing_score=passing, is_published=True)
        session.add(e)
        session.commit()
        session.refresh(e)
        print(f"  [ok]   evaluación '{title}' creada")
        return e

    def add_question(evaluation: TrainingEvaluation, question: str, options: list, correct: int, points: int, order: int) -> None:
        existing = session.exec(
            select(TrainingQuizQuestion).where(
                TrainingQuizQuestion.evaluation_id == evaluation.id,
                TrainingQuizQuestion.order_index == order,
            )
        ).first()
        if existing:
            print(f"  [skip] pregunta orden {order} de '{evaluation.title}' ya existe")
            return
        q = TrainingQuizQuestion(
            evaluation_id=evaluation.id, question=question, options=options,
            correct_option=correct, points=points, order_index=order,
        )
        session.add(q)
        session.commit()
        all_questions = session.exec(
            select(TrainingQuizQuestion).where(TrainingQuizQuestion.evaluation_id == evaluation.id)
        ).all()
        evaluation.max_score = sum(qq.points for qq in all_questions)
        session.add(evaluation)
        session.commit()
        print(f"  [ok]   pregunta {order + 1} de '{evaluation.title}' creada")

    def enroll_docente(program: TrainingProgram, docente_email: str, trainer_email: str) -> None:
        docente = get_user(docente_email)
        trainer = get_user(trainer_email)
        if docente is None:
            print(f"  [warn] '{docente_email}' no existe, saltando inscripción")
            return
        existing = session.exec(select(TrainingEnrollment).where(
            TrainingEnrollment.program_id == program.id,
            TrainingEnrollment.user_id == docente.id,
        )).first()
        if existing:
            print(f"  [skip] '{docente_email}' ya inscrito en '{program.name}'")
            return
        enrollment = TrainingEnrollment(
            program_id=program.id, user_id=docente.id,
            enrolled_by=trainer.id, enrolled_at=datetime.now(timezone.utc),
        )
        session.add(enrollment)
        session.commit()
        print(f"  [ok]   '{docente_email}' inscrito en '{program.name}'")

    # ── Programa 1: Robótica Educativa ──
    p1 = get_or_create_program(
        "Capacitación en Robótica Educativa",
        "Programa oficial de RobotSchool para docentes",
        "Capacitar docentes en el uso de herramientas de robótica en el aula",
        20, "trainer@robotschool.com",
    )
    p1_m1 = get_or_create_module(p1, "Introducción a la Robótica", 0)
    get_or_create_lesson(p1_m1, "¿Qué es la robótica educativa?", "TEXT",
        "La robótica educativa es una herramienta pedagógica que permite aprender STEM a través de la construcción y programación de robots.", 0)
    get_or_create_lesson(p1_m1, "Historia de la robótica en el aula", "TEXT",
        "Desde los años 80 con Logo Turtle hasta los kits modernos de Lego Mindstorms y Arduino, la robótica ha evolucionado en la educación.", 1)
    get_or_create_lesson(p1_m1, "Video: Primeros pasos con Lego", "VIDEO",
        "https://example.com/video-lego-intro", 2)
    ev1 = get_or_create_evaluation(p1_m1, "Quiz de Introducción", "QUIZ", 60)
    add_question(ev1, "¿Cuál es el objetivo principal de la robótica educativa?",
        [{"id": 0, "text": "Entretenimiento"}, {"id": 1, "text": "Desarrollo del pensamiento computacional"}, {"id": 2, "text": "Competencia deportiva"}, {"id": 3, "text": "Ninguna de las anteriores"}],
        1, 10, 0)
    add_question(ev1, "¿Qué significa STEM?",
        [{"id": 0, "text": "Science, Technology, Engineering, Mathematics"}, {"id": 1, "text": "Sports, Tech, Education, Media"}, {"id": 2, "text": "Skills, Training, Experience, Methods"}, {"id": 3, "text": "Ninguna"}],
        0, 10, 1)
    add_question(ev1, "¿Qué kit de robótica es el más usado en primaria?",
        [{"id": 0, "text": "Arduino Mega"}, {"id": 1, "text": "Raspberry Pi"}, {"id": 2, "text": "Lego WeDo / Mindstorms"}, {"id": 3, "text": "Raspberry Pi Pico"}],
        2, 10, 2)

    p1_m2 = get_or_create_module(p1, "Programación por Bloques", 1)
    get_or_create_lesson(p1_m2, "Introducción a Scratch", "TEXT",
        "Scratch es un lenguaje de programación visual desarrollado por el MIT. Permite crear historias, juegos y animaciones.", 0)
    get_or_create_lesson(p1_m2, "Condicionales y bucles en Scratch", "TEXT",
        "Los bloques de control permiten crear lógica: si/sino, repetir, esperar. Son la base del pensamiento algorítmico.", 1)
    get_or_create_lesson(p1_m2, "Video: Proyecto guiado en Scratch", "VIDEO",
        "https://example.com/video-scratch-proyecto", 2)
    ev2 = get_or_create_evaluation(p1_m2, "Quiz Programación por Bloques", "QUIZ", 70)
    add_question(ev2, "¿Qué bloque se usa para repetir acciones en Scratch?",
        [{"id": 0, "text": "Bloque 'mover'"}, {"id": 1, "text": "Bloque 'repetir'"}, {"id": 2, "text": "Bloque 'decir'"}, {"id": 3, "text": "Bloque 'esperar'}]"},],
        1, 10, 0)
    add_question(ev2, "¿Cuál es el evento inicial más común en Scratch?",
        [{"id": 0, "text": "Al hacer clic en el objeto"}, {"id": 1, "text": "Al presionar la tecla espacio"}, {"id": 2, "text": "Al hacer clic en la bandera verde"}, {"id": 3, "text": "Al iniciar el programa"}],
        2, 10, 1)
    ev3 = get_or_create_evaluation(p1_m2, "Tarea: Crear un proyecto en Scratch", "ASSIGNMENT", 60)

    p1_m3 = get_or_create_module(p1, "Sensores y Actuadores", 2)
    get_or_create_lesson(p1_m3, "¿Qué son los sensores?", "TEXT",
        "Los sensores permiten al robot percibir el entorno: distancia, color, luz, sonido. Son los 'sentidos' del robot.", 0)
    get_or_create_lesson(p1_m3, "Motores y servos", "TEXT",
        "Los actuadores permiten al robot moverse y actuar sobre el entorno. Los motores DC y los servos son los más comunes.", 1)
    ev4 = get_or_create_evaluation(p1_m3, "Quiz Sensores y Actuadores", "QUIZ", 60)
    add_question(ev4, "¿Qué tipo de sensor mide la distancia a un obstáculo?",
        [{"id": 0, "text": "Sensor de color"}, {"id": 1, "text": "Sensor ultrasónico"}, {"id": 2, "text": "Sensor de luz"}, {"id": 3, "text": "Sensor de temperatura"}],
        1, 10, 0)

    # Inscripciones Programa 1
    for email in ["docente1@sanpedro.edu.co", "docente2@sanpedro.edu.co",
                  "docente1@lasalle.edu.co", "docente1@losandes.edu.co"]:
        enroll_docente(p1, email, "trainer@robotschool.com")

    # ── Programa 2: FLL para Docentes ──
    p2 = get_or_create_program(
        "FLL para Docentes — Guía de Entrenadores",
        "Programa de formación para coaches de First Lego League",
        "Formar docentes como entrenadores certificados de FLL",
        15, "trainer2@robotschool.com",
    )
    p2_m1 = get_or_create_module(p2, "¿Qué es FLL?", 0)
    get_or_create_lesson(p2_m1, "Historia y estructura de FLL", "TEXT",
        "First Lego League (FLL) es una competencia internacional de robótica para estudiantes de 9 a 16 años, organizada por FIRST y Lego Education.", 0)
    get_or_create_lesson(p2_m1, "Las 3 misiones de FLL", "TEXT",
        "FLL tiene tres componentes: Robot Game (misiones en la mesa), Innovation Project (investigación) y Core Values (trabajo en equipo).", 1)
    ev5 = get_or_create_evaluation(p2_m1, "Quiz FLL Básico", "QUIZ", 60)
    add_question(ev5, "¿Cuántos componentes tiene FLL?",
        [{"id": 0, "text": "1"}, {"id": 1, "text": "2"}, {"id": 2, "text": "3"}, {"id": 3, "text": "4"}],
        2, 10, 0)
    add_question(ev5, "¿Qué kit usa FLL actualmente?",
        [{"id": 0, "text": "Lego WeDo"}, {"id": 1, "text": "Lego Spike Prime"}, {"id": 2, "text": "Lego Mindstorms EV3"}, {"id": 3, "text": "Arduino"}],
        1, 10, 1)

    p2_m2 = get_or_create_module(p2, "Robot Game — Estrategia", 1)
    get_or_create_lesson(p2_m2, "Tabla de misiones y puntuación", "TEXT",
        "Cada año FLL publica un reto nuevo. Las misiones tienen distintos valores de puntos. El equipo debe priorizar según su estrategia.", 0)
    get_or_create_lesson(p2_m2, "Diseño del robot base", "TEXT",
        "El robot debe ser robusto, fácil de reparar y capaz de ejecutar attachments. El diseño base define el éxito en competencia.", 1)
    ev6 = get_or_create_evaluation(p2_m2, "Tarea: Plan de misiones", "ASSIGNMENT", 60)

    for email in ["docente2@lasalle.edu.co", "docente2@losandes.edu.co", "docente2@sanpedro.edu.co"]:
        enroll_docente(p2, email, "trainer2@robotschool.com")

    # ── Programa 3: Minecraft Education (inactivo — para probar estados) ──
    p3 = get_or_create_program(
        "Minecraft Education para el Aula",
        "Uso pedagógico de Minecraft Education Edition",
        "Implementar Minecraft como herramienta de aprendizaje colaborativo",
        10, "trainer3@robotschool.com",
        is_active=False,
    )
    p3_m1 = get_or_create_module(p3, "Introducción a Minecraft Education", 0)
    get_or_create_lesson(p3_m1, "¿Qué es Minecraft Education?", "TEXT",
        "Minecraft Education Edition es una versión de Minecraft diseñada para el aula, con herramientas para docentes y estudiantes.", 0)


# ── Repositorio ───────────────────────────────────────────────────────────────

def seed_repository(session: Session) -> None:
    from app.domains.repository.models.repository_folder import RepositoryFolder
    from app.domains.repository.models.repository_file import RepositoryFile

    admin = session.exec(select(User).where(User.email == "admin@robotschool.com")).first()
    if admin is None:
        print("  [warn] admin no existe, saltando repositorio")
        return

    import uuid as _uuid

    def get_or_create_folder(name: str, description: str, parent_id: int | None = None) -> RepositoryFolder:
        f = session.exec(
            select(RepositoryFolder).where(
                RepositoryFolder.name == name,
                RepositoryFolder.parent_id == parent_id,
            )
        ).first()
        if f:
            print(f"  [skip] carpeta '{name}' ya existe")
            return f
        now = datetime.now(timezone.utc)
        f = RepositoryFolder(
            public_id=str(_uuid.uuid4()),
            name=name,
            description=description,
            parent_id=parent_id,
            created_by=admin.id,
            created_at=now,
            updated_at=now,
        )
        session.add(f)
        session.commit()
        session.refresh(f)
        print(f"  [ok]   carpeta '{name}' creada")
        return f

    root_rb   = get_or_create_folder("Robótica Educativa",   "Materiales del programa de robótica educativa")
    root_fll  = get_or_create_folder("FLL",                  "Recursos para First Lego League")
    root_mc   = get_or_create_folder("Minecraft Education",  "Materiales de Minecraft Education Edition")
    root_gen  = get_or_create_folder("General",              "Documentos y recursos generales")

    get_or_create_folder("Módulo 1 — Introducción",     "Lecciones y materiales del módulo 1",       root_rb.id)
    get_or_create_folder("Módulo 2 — Programación",     "Lecciones y materiales del módulo 2",       root_rb.id)
    get_or_create_folder("Módulo 3 — Sensores",         "Lecciones y materiales del módulo 3",       root_rb.id)
    get_or_create_folder("Robot Game",                  "Estrategias y guías del Robot Game",        root_fll.id)
    get_or_create_folder("Innovation Project",          "Guías de investigación y presentación",     root_fll.id)
    get_or_create_folder("Core Values",                 "Actividades de trabajo en equipo",          root_fll.id)
    get_or_create_folder("Guías Docente",               "Guías pedagógicas para docentes",           root_gen.id)
    get_or_create_folder("Plantillas Certificados",     "Plantillas PNG para certificados",          root_gen.id)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("→ Iniciando seed...")
    with Session(engine) as session:
        print("\n→ Roles RBAC:")
        seed_roles(session)

        print("\n→ Usuarios:")
        seed_users(session)

        print("\n→ Ubicaciones de stock:")
        seed_locations(session)

        print("\n→ Académico:")
        seed_academic(session)

        print("\n→ Capacitación:")
        seed_training(session)

        print("\n→ Repositorio (carpetas):")
        seed_repository(session)

        print("\n→ Asignación de roles:")
        seed_user_roles(session)

    print("\n✓ Seed completo.")


if __name__ == "__main__":
    main()
