#!/usr/bin/env python3
"""Corrige matrículas mal puestas a partir de un CSV `email;grupo`.

Para cada fila deja al estudiante matriculado EXACTAMENTE en `grupo` dentro del
colegio: lo inscribe en el curso correcto y lo saca (soft delete) de cualquier
otro curso activo del mismo colegio. Pensado para el reinicio de ciclo, donde
cada estudiante pertenece a un solo grupo.

Diseño (igual espíritu que el importador):
  - **Todo-o-nada**: valida TODAS las filas antes de tocar nada. Si alguna falla
    (email no existe, grupo no existe, email duplicado en el CSV), aborta sin
    escribir y reporta qué corregir.
  - **Idempotente**: si el estudiante ya está solo en el grupo correcto, no hace
    nada. Reejecutar es seguro.
  - **Reversible**: sacar de un curso es soft delete (`is_active=false`).
  - **Dry-run por defecto**: muestra el plan sin aplicar. Para ejecutar de verdad,
    pasar `--apply`.

Uso dentro del contenedor (datos de menores → el CSV vive en el VPS, no en git):
    docker exec -i rbsoftware-backend python scripts/corregir_matriculas.py \
        --csv /tmp/correcciones.csv            # dry-run: muestra el plan
    docker exec -i rbsoftware-backend python scripts/corregir_matriculas.py \
        --csv /tmp/correcciones.csv --apply    # aplica los cambios

    # School por defecto = 1 (Colegio RobotSchool). Cambiar con --school-id N.

Formato del CSV de correcciones (delimitador ; o ,):
    email;grupo
    estudiante@correo.edu.co;TERCERO
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from difflib import get_close_matches
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, create_engine, select

from app.core.config import settings
from app.domains.academic.models.lms_course import LmsCourse
from app.domains.academic.models.lms_course_student import LmsCourseStudent
from app.domains.academic.models.school import School
from app.domains.academic.repositories.course_student_repository import (
    CourseStudentRepository,
)
from app.domains.audit.services import AuditService
from app.domains.auth.models import User
from app.domains.auth.services.user_service import _normalize_group

engine = create_engine(settings.database_url)
_audit = AuditService()


def _read_rows(csv_path: str) -> list[dict]:
    raw = Path(csv_path).read_bytes()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw.decode("cp1252")
    first_line = content.split("\n")[0]
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    headers = {(h or "").strip().lower() for h in (reader.fieldnames or [])}
    missing = {"email", "grupo"} - headers
    if missing:
        sys.exit(f"ERROR: faltan columnas en el CSV: {', '.join(sorted(missing))}")
    return list(reader)


def main() -> int:
    parser = argparse.ArgumentParser(description="Corrige matrículas desde un CSV email;grupo")
    parser.add_argument("--csv", required=True, help="Ruta del CSV de correcciones")
    parser.add_argument("--school-id", type=int, default=1, help="ID del colegio (default 1)")
    parser.add_argument("--apply", action="store_true", help="Aplica los cambios (sin esto: dry-run)")
    args = parser.parse_args()

    rows = _read_rows(args.csv)

    with Session(engine) as session:
        school = session.get(School, args.school_id)
        if school is None:
            sys.exit(f"ERROR: no existe colegio con id={args.school_id}")

        courses = session.exec(
            select(LmsCourse).where(
                LmsCourse.school_id == school.id,
                LmsCourse.is_active == True,  # noqa: E712
            )
        ).all()
        course_by_group = {_normalize_group(c.name): c for c in courses}
        group_keys = list(course_by_group.keys())
        course_by_id = {c.id: c for c in courses}
        school_course_ids = set(course_by_id)

        print(f"Colegio: {school.name} (id={school.id}) — {len(courses)} cursos activos")
        print(f"Modo: {'APLICAR' if args.apply else 'DRY-RUN (no se escribe nada)'}\n")

        # ── Validación todo-o-nada ───────────────────────────────────────────
        errors: list[str] = []
        valid: list[dict] = []
        seen: set[str] = set()

        for i, row in enumerate(rows, start=2):
            email = (row.get("email") or "").strip().lower()
            grupo_raw = (row.get("grupo") or "").strip()

            if not email or not grupo_raw:
                errors.append(f"fila {i}: email y grupo son obligatorios")
                continue
            if email in seen:
                errors.append(f"fila {i}: email duplicado dentro del CSV ({email})")
                continue
            seen.add(email)

            user = session.exec(select(User).where(User.email == email)).first()
            if user is None:
                errors.append(f"fila {i}: no existe usuario con email {email}")
                continue

            course = course_by_group.get(_normalize_group(grupo_raw))
            if course is None:
                sug = get_close_matches(_normalize_group(grupo_raw), group_keys, n=1, cutoff=0.6)
                hint = f' — ¿quisiste decir "{course_by_group[sug[0]].name}"?' if sug else ""
                errors.append(f'fila {i}: grupo "{grupo_raw}" no existe en el colegio{hint}')
                continue

            valid.append({"user": user, "course": course, "email": email})

        if errors:
            print("ABORTADO — no se escribió nada. Corrige y reejecuta:\n")
            for e in errors:
                print(f"  ✗ {e}")
            return 1

        # ── Plan por estudiante ──────────────────────────────────────────────
        repo = CourseStudentRepository(session)
        changes = 0

        for entry in valid:
            user = entry["user"]
            target = entry["course"]

            active = session.exec(
                select(LmsCourseStudent).where(
                    LmsCourseStudent.user_id == user.id,
                    LmsCourseStudent.is_active == True,  # noqa: E712
                    LmsCourseStudent.course_id.in_(school_course_ids),
                )
            ).all()
            active_course_ids = {r.course_id for r in active}
            wrong_ids = active_course_ids - {target.id}
            already_ok = target.id in active_course_ids

            if not wrong_ids and already_ok:
                print(f"  = {entry['email']}: ya está solo en {target.name} (sin cambios)")
                continue

            wrong_names = ", ".join(course_by_id[cid].name for cid in wrong_ids) or "(ninguno)"
            action_desc = []
            if not already_ok:
                action_desc.append(f"INSCRIBIR en {target.name}")
            if wrong_ids:
                action_desc.append(f"SACAR de {wrong_names}")
            print(f"  → {entry['email']}: {' + '.join(action_desc)}")
            changes += 1

            if args.apply:
                from_id = next(iter(wrong_ids)) if wrong_ids else None
                repo.enroll(target.id, user.id, from_course_id=from_id)
                for cid in wrong_ids:
                    repo.unenroll(cid, user.id)
                _audit.log(
                    session,
                    user_id=None,
                    action="academic.student.enrollment_corrected",
                    resource_type="lms_course_student",
                    resource_id=str(user.id),
                    payload={
                        "to_course_id": target.id,
                        "removed_from_course_ids": sorted(wrong_ids),
                        "via": "corregir_matriculas.py",
                    },
                )

        print()
        if not args.apply:
            print(f"DRY-RUN: {changes} estudiante(s) cambiarían. Reejecuta con --apply para aplicar.")
        else:
            print(f"LISTO: {changes} estudiante(s) corregido(s).")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
