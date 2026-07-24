# Spec — Multi-docente por curso (`lms_course_teachers`)

> Estado: **aprobado para implementar**. Deriva del ADR "Multi-docente por curso en
> RBSoftware LMS (expand/contract)". Este documento es el contrato que consumen
> `coder-migracion-modelo`, `coder-backend`, `coder-frontend` y `reviewer-permisos`.
>
> Inventario verificado contra el código real en `main` (`5f5455e`) el 2026-07-24,
> archivo por archivo y línea por línea. Donde el ADR y el código no coinciden,
> manda el código y queda anotado como **[corrección al ADR]**.

---

## 1. Modelo y migración

### 1.1 Estado actual

`backend/app/domains/academic/models/lms_course.py:29-33`

```python
teacher_id: int = Field(
    sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
)
```

Es decir: **un curso = exactamente un docente**, FK `NOT NULL` con `ondelete=CASCADE`
(borrar un usuario borra sus cursos — riesgo aparte, fuera de alcance de este PR).

### 1.2 Tabla nueva

`backend/app/domains/academic/models/lms_course_teacher.py` (clon de
`models/school_teacher.py`, que es el patrón ya usado en el dominio para colegio↔docente):

```python
class LmsCourseTeacher(SQLModel, table=True):
    __tablename__ = "lms_course_teachers"
    __table_args__ = (
        UniqueConstraint("course_id", "user_id", name="uq_lms_course_teachers_course_user"),
    )

    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(
        sa_column=Column(Integer, ForeignKey("lms_courses.id", ondelete="CASCADE"), nullable=False)
    )
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
```

**`ondelete` — por qué distinto en cada FK:**

| FK | Política | Motivo |
|---|---|---|
| `course_id → lms_courses.id` | `CASCADE` | Si el curso desaparece, su lista de docentes no significa nada. Igual que `school_teachers`. |
| `user_id → users.id` | `RESTRICT` | Borrar un usuario **no** debe borrar en silencio el registro de qué cursos dictó. Debe fallar y forzar una decisión explícita. Es deliberadamente más estricto que `school_teachers` (que usa `CASCADE`). |

> **Riesgo a verificar antes de mergear:** `RESTRICT` hace que cualquier flujo que
> hoy borre usuarios empiece a fallar con `IntegrityError` si el usuario es docente
> de algún curso. Hoy ese borrado "funciona" porque `lms_courses.teacher_id` tiene
> `CASCADE` — o sea, se lleva el curso por delante. El reviewer debe buscar
> (`grep -rn "session.delete(user\|delete_user"`) si existe una ruta de borrado de
> usuarios y confirmar que el nuevo error se maneja con un 400 legible, no con un 500.

### 1.3 Migración Alembic

- Archivo: `backend/alembic/versions/t5u6v7w8x9y0_add_lms_course_teachers.py`
- `revision = "t5u6v7w8x9y0"`, `down_revision = "s4t5u6v7w8x9"`
- **HEAD confirmado:** `s4t5u6v7w8x9` (`add_logro_to_lms_assignments`) — ningún otro
  archivo lo declara como `down_revision`, así que no se crea rama.

**Upgrade (expand — no se borra `teacher_id` en este PR):**

```python
def upgrade():
    op.create_table(
        "lms_course_teachers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_id", sa.Integer(),
                  sa.ForeignKey("lms_courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("course_id", "user_id", name="uq_lms_course_teachers_course_user"),
    )
    op.execute("""
        INSERT INTO lms_course_teachers (course_id, user_id, created_at)
        SELECT id, teacher_id, NOW() FROM lms_courses WHERE teacher_id IS NOT NULL
    """)
    op.alter_column("lms_courses", "teacher_id", existing_type=sa.Integer(), nullable=True)
```

**Downgrade — [corrección al ADR]:** el ADR ponía el `ALTER ... NOT NULL` **antes**
del `UPDATE`. Eso revienta si existe cualquier curso creado después del upgrade con
`teacher_id` NULL. El orden correcto es: abortar si hay multi-docente → repoblar →
recién ahí volver a `NOT NULL` → soltar la tabla.

```python
def downgrade():
    conn = op.get_bind()
    multi = conn.execute(sa.text(
        "SELECT course_id FROM lms_course_teachers GROUP BY course_id HAVING COUNT(*) > 1"
    )).fetchall()
    if multi:
        raise RuntimeError(
            f"Downgrade abortado: {len(multi)} curso(s) tienen más de un docente; "
            "resolver a mano antes de bajar la migración."
        )
    # 1) repoblar la columna legacy ANTES de exigir NOT NULL
    op.execute("""
        UPDATE lms_courses c
        JOIN lms_course_teachers ct ON ct.course_id = c.id
        SET c.teacher_id = ct.user_id
    """)
    # 2) si aún queda algún curso sin docente, NOT NULL fallaría: abortar legible
    huerfanos = conn.execute(sa.text(
        "SELECT COUNT(*) FROM lms_courses WHERE teacher_id IS NULL"
    )).scalar()
    if huerfanos:
        raise RuntimeError(
            f"Downgrade abortado: {huerfanos} curso(s) sin docente asignado; "
            "asignar uno antes de bajar la migración."
        )
    op.alter_column("lms_courses", "teacher_id", existing_type=sa.Integer(), nullable=False)
    op.drop_table("lms_course_teachers")
```

**Verificación de integridad (nota de PR, ejecutar contra copia de datos reales):**

```sql
SELECT COUNT(*) FROM lms_courses WHERE teacher_id IS NOT NULL;  -- antes
SELECT COUNT(*) FROM lms_course_teachers;                        -- después → debe coincidir
```

---

## 2. Inventario línea a línea

Leyenda: **MIGRA** = se reescribe · **QUEDA** = no se toca (con motivo) · **NUEVO**.

### 2.1 `backend/app/domains/academic/models/lms_course.py`

| Línea | Código actual | Acción |
|---|---|---|
| 29-33 | `teacher_id: int = Field(... nullable=False)` | **MIGRA** → `teacher_id: int \| None`, `nullable=True`. El `ondelete="CASCADE"` existente **no se toca** (no es el foco). |

### 2.2 `backend/app/domains/academic/repositories/course_repository.py`

| Línea | Código actual | Acción |
|---|---|---|
| 21 | `teacher_id: int \| None` en `create()` | **QUEDA** — la creación sigue aceptando un docente inicial. |
| 29 | `"teacher_id": teacher_id` en el `update=` de `model_validate` | **QUEDA** — puebla la columna legacy. El *service* es responsable de sembrar además la fila puente (§3.4). |
| 52-58 | `list_by_teacher()` filtra `LmsCourse.teacher_id == teacher_id` | **MIGRA** → `JOIN lms_course_teachers ON course_id = lms_courses.id WHERE user_id = :teacher_id AND is_active` |
| 114-119 | `set_teacher(course, teacher_id)` | **MIGRA** → se **elimina**. Nadie más debe reemplazar el docente único. |

`list_by_teacher` migrado:

```python
def list_by_teacher(self, teacher_id: int) -> list[LmsCourse]:
    stmt = (
        select(LmsCourse)
        .join(LmsCourseTeacher, LmsCourseTeacher.course_id == LmsCourse.id)
        .where(LmsCourseTeacher.user_id == teacher_id, LmsCourse.is_active.is_(True))
        .order_by(LmsCourse.name)
    )
    return list(self.session.exec(stmt).all())
```

### 2.3 `backend/app/domains/academic/repositories/course_teacher_repository.py` — **NUEVO**

Clon 1:1 de `school_teacher_repository.py` cambiando `school_id → course_id`:

| Método | Firma | Notas |
|---|---|---|
| `add` | `(course_id: int, user_id: int) -> LmsCourseTeacher` | Idempotente: si ya existe, devuelve el registro (mismo comportamiento que `SchoolTeacherRepository.add`). |
| `remove` | `(course_id, user_id) -> bool` | `False` si no existía. |
| `get_teacher_ids` | `(course_id) -> list[int]` | |
| `is_course_teacher` | `(course_id, user_id) -> bool` | Base del helper de pertenencia. |
| `list_teachers` | `(course_id) -> list[User]` | JOIN a `User`, `ORDER BY first_name, last_name`. |
| `list_course_ids_for_teacher` | `(user_id) -> list[int]` | Para `remove_teacher_from_school`. |
| `_get_record` | privado | |

Registrar la clase en `repositories/__init__.py` y el modelo en `models/__init__.py`
(patrón existente del dominio — si no se registra, Alembic autogenerate no lo ve).

### 2.4 `backend/app/domains/academic/services/academic_service.py`

Este archivo concentra el riesgo. **Cero comparaciones `== / != course.teacher_id`
deben sobrevivir** al diff.

| Línea | Código actual | Acción |
|---|---|---|
| 105 | `if course.teacher_id == user_id:` (en `_assert_admin_or_director_or_teacher`) | **MIGRA** → `if self._is_course_teacher(session, course.id, user_id):` |
| 116 | `if course.teacher_id == user_id:` (en `_assert_admin_or_teacher`) | **MIGRA** → mismo helper |
| 170 | `if c.teacher_id == user_id and c.is_active` (en `remove_teacher_from_school`) | **MIGRA** → intersección de `list_course_ids_for_teacher(user_id)` con los cursos activos del colegio |
| 431 | `teacher_ids = {c.id for c in teacher_courses}` | **QUEDA** — mal nombrada, pero es un set de **course ids**, no de docentes. No renombrar en este PR para no ensuciar el diff. |
| 444 | `t_ids = {c.teacher_id for c in all_courses}` | **MIGRA** → `get_teacher_ids(c.id)` por curso (una sola query agrupada, ver §3.2) |
| 458 | `teacher = teachers_map.get(c.teacher_id)` | **MIGRA** → lista de docentes del curso |
| 469-471 | `teacher_name=f"{first} {last}"` | **MIGRA** → `teacher_names: list[str]` |
| 472 | `role="TEACHER" if c.id in teacher_ids else "STUDENT"` | **QUEDA** — deriva de `get_my_courses_as_teacher`, ya corregido río arriba vía `list_by_teacher` |
| 483 | `teacher = UserRepository(session).get_by_id(course.teacher_id)` (en `get_course_detail`) | **MIGRA** → `CourseTeacherRepository(session).list_teachers(course.id)` |
| 493 | `teacher=UserRead.model_validate(teacher)` | **MIGRA** → `teachers=[UserRead.model_validate(t) for t in teachers]` |
| 503-516 | `create_course(..., teacher_id: int, ...)` | **QUEDA la firma**; se **agrega** `CourseTeacherRepository(session).add(course.id, teacher_id)` tras el `create` (§3.4) |
| 631 | `"teacher_id": course.teacher_id` en el payload de auditoría del borrado | **MIGRA** → `"teacher_ids": get_teacher_ids(course.id)` capturado **antes** del delete (el `CASCADE` borra las filas puente) |
| 684-687 | `if course.teacher_id is not None and course.teacher_id not in candidates` | **MIGRA** → recorrer todos los docentes actuales del curso e incluirlos si faltan |
| 698-723 | `assign_teacher()` → `set_teacher` (reemplaza) | **MIGRA** → `add_teacher_to_course()` (agrega) + **NUEVO** `remove_teacher_from_course()` |
| 747 | `if course.teacher_id == user_id:` (bloqueo en `enroll_student`) | **MIGRA** → `if self._is_course_teacher(session, course.id, user_id):` |
| 1141 | `is_teacher = course.teacher_id == requesting_user_id` (`get_material_view_url`) | **MIGRA** → helper |
| 1304 | `teacher_id: int` param de `grade_submission` | **QUEDA** — es "quién califica", no pertenencia |
| 1314 | `self._assert_admin_or_teacher(session, course, teacher_id)` | **QUEDA** — ya cubierto al migrar el helper (línea 116) |
| 1327 | `graded_by=teacher_id` | **QUEDA** — atribución puntual del calificador, FK simple. **No es pertenencia.** |
| 1334 | `user_id=teacher_id` en el audit log | **QUEDA** |
| 1361 | `if course.teacher_id != requesting_user_id:` (`get_submission_view_url`) | **MIGRA** → `if not self._is_course_teacher(...)` |
| 1528 | `return CourseRepository(session).list_by_teacher(user_id)` | **QUEDA** — corregido río arriba en el repo (§2.2) |
| 1564 | `is_teacher = course.teacher_id == requesting_user_id` (`get_course_content`) | **MIGRA** → helper |

### 2.5 `backend/app/domains/academic/routes/courses.py`

| Línea | Código actual | Acción |
|---|---|---|
| 31-32 | `class TeacherBody: teacher_id: UUID` | **QUEDA la clase**, la reusa el nuevo POST plural |
| 71-83 | `GET /courses/{id}` → `response_model=CourseDetail` | **QUEDA la ruta**; cambia el shape porque cambia el schema (§4.1) |
| 103-119 | `GET /courses/{id}/assignable-teachers` (ADMIN, DIRECTOR) | **QUEDA la ruta**; cambia la lógica de exclusión (§2.4 línea 684) |
| 122-140 | `POST /courses/{id}/teacher` (ADMIN, DIRECTOR) — reemplaza | **MIGRA** → se **elimina** y se reemplaza por `POST /courses/{id}/teachers` (agrega), **ADMIN-only** |
| — | — | **NUEVO** `DELETE /courses/{id}/teachers/{user_id}`, ADMIN-only |

### 2.6 `backend/app/domains/academic/routes/grades.py`

| Línea | Código actual | Acción |
|---|---|---|
| 28-29 | `class CourseCreateBody(CourseCreate): teacher_id: UUID` | **QUEDA** — la creación sigue con un docente inicial obligatorio. [corrección al ADR: no es un `TeacherBody` duplicado, es el body de creación de curso; no hay ruta de asignación en este archivo.] |
| 162 | `teacher = UserRepository(session).get_by_public_id(body.teacher_id)` | **QUEDA** — resuelve el docente inicial. `body.teacher_id` ya llega como `UUID` tipado por FastAPI. |

### 2.7 `backend/app/domains/auth/routes/users.py`

| Línea | Código actual | Acción |
|---|---|---|
| 78-79 | `if course.teacher_id: user_ids.add(course.teacher_id)` | **MIGRA** → `user_ids.update(CourseTeacherRepository(session).get_teacher_ids(course.id))`. Es el puente `users-sync` hacia el portal: si no migra, los co-docentes no se sincronizan. |

### 2.8 Schemas

| Archivo:línea | Actual | Nuevo |
|---|---|---|
| `schemas/lms_course.py:39` | `teacher_name: str` | `teacher_names: list[str]` |
| `schemas/composite.py:41` | `teacher: UserRead` | `teachers: list[UserRead] = []` |

### 2.9 Tests

| Archivo:línea | Actual | Acción |
|---|---|---|
| `backend/tests/test_import_csv.py:78` | `LmsCourse(name=cname, teacher_id=teacher.id, ...)` en el fixture | **QUEDA** — construye el modelo directo, y `teacher_id` sigue existiendo. **Pero** si el test ejercita algo que lea docentes vía el nuevo repo, el fixture debe además insertar `LmsCourseTeacher(course_id=..., user_id=teacher.id)`. Verificar al correr. |

**Tests nuevos exigidos** (hoy no hay tests de este flujo — es un hueco, no una omisión del inventario):
1. `add_teacher_to_course` es idempotente (dos llamadas → una fila).
2. Un segundo docente agregado pasa `_assert_admin_or_teacher` y puede calificar.
3. Un docente removido pierde el acceso en el mismo request siguiente.
4. `DELETE` del último docente → `400`, no deja el curso huérfano.
5. `POST`/`DELETE` → `403` para `DIRECTOR` y `TEACHER`.

### 2.10 Frontend — **[corrección al ADR]**

El ADR listaba 2 archivos. Son **7**: `CourseDetail.teacher` se consume en cinco
lugares y romper el schema sin tocarlos deja pantallas en blanco.

| Archivo:línea | Actual | Acción |
|---|---|---|
| `lib/types.ts:280` | `teacher_name: string` en `MyCourseRead` | → `teacher_names: string[]` |
| `lib/types.ts:291` | `teacher: User` en `CourseDetail` | → `teachers: User[]` |
| `services/academic.ts:134-136` | `assignCourseTeacher` → `POST .../teacher` | → `addCourseTeacher` → `POST .../teachers`; **NUEVO** `removeCourseTeacher` → `DELETE .../teachers/{userId}` |
| `services/academic.ts:125` | `createCourse(..., teacher_id)` | **QUEDA** — docente inicial |
| `components/academic/CreateCourseModal.tsx:38` | `teacher_id: teacherId` | **QUEDA** — selector único en creación, por diseño |
| `components/academic/CourseDetailView.tsx:41` | `course.teacher.public_id === user?.public_id` | → `course.teachers.some(t => t.public_id === user?.public_id)` |
| `components/academic/TeacherCourseView.tsx:69,88` | `currentTeacherId={course.teacher.public_id}` y el render del nombre | → lista de docentes con acciones agregar/quitar (solo ADMIN); el modal de asignación recibe los IDs ya asignados para excluirlos |
| `components/academic/StudentCourseView.tsx:42` | `Docente: {course.teacher.first_name} ...` | → `Docentes: ` unidos por `, ` |
| `components/academic/MyCoursesView.tsx:85` | `{c.teacher_name}` | → `{c.teacher_names.join(', ')}` |
| `hooks/useGradeDetail.ts:8,47` | `teacher: User \| null` ← `d.teacher` | → `teachers: User[]` ← `d.teachers`; `GradeDetailView.tsx:208-211` renderiza la lista o `—` |

### 2.11 Fuera de alcance (explícito)

- `repositories/school_teacher_repository.py` y la tabla `school_teachers`: es
  membresía de **colegio** (qué docentes pueden dictar ahí), no de curso.
- `graded_by` en `lms_submissions`: atribución puntual de quién calificó una entrega,
  no una relación de asignación vigente.
- **No se borra** `lms_courses.teacher_id` en este PR (contract = PR futuro,
  **agendar explícitamente** para que no quede en limbo).
- El `ondelete="CASCADE"` de `lms_courses.teacher_id` sigue como está.

---

## 3. Reglas de implementación

### 3.1 Helper canónico de pertenencia

```python
def _is_course_teacher(self, session: Session, course_id: int, user_id: int) -> bool:
    return CourseTeacherRepository(session).is_course_teacher(course_id, user_id)
```

Toda pertenencia pasa por aquí. La barra de aceptación del reviewer es un grep:

```bash
grep -rn "teacher_id ==\|teacher_id !=\|== .*teacher_id" backend/app
```

Debe salir **vacío** salvo: `graded_by`, el parámetro `teacher_id` de `grade_submission`,
y la columna legacy en `CourseRepository.create()`.

### 3.2 N+1 en `get_my_courses`

`get_my_courses` ya arma mapas por lote (`grades_map`, `schools_map`). No reemplazar
eso por un `list_teachers()` por curso dentro del loop: para un ADMIN,
`get_my_courses_as_teacher` devuelve **todos** los cursos activos, así que serían N
queries. Resolver con una sola query agrupada:

```python
rows = session.exec(
    select(LmsCourseTeacher.course_id, User)
    .join(User, User.id == LmsCourseTeacher.user_id)
    .where(LmsCourseTeacher.course_id.in_([c.id for c in all_courses]))
    .order_by(User.first_name, User.last_name)
).all()
teachers_by_course: dict[int, list[User]] = defaultdict(list)
for course_id, user in rows:
    teachers_by_course[course_id].append(user)
```

### 3.3 Coerción a `uuid.UUID` (trampa del 500 conocido)

`LmsCourse.public_id` y `User.public_id` son `Uuid(as_uuid=True, native_uuid=False)`.
Comparar esa columna contra un `str` crudo produce
`'str' object has no attribute 'hex'` → **500** (ya pasó en `create_folder_share`).

Regla: **toda** comparación contra una columna `Uuid` recibe un `uuid.UUID`, no un `str`.

- Los path params tipados `course_id: UUID` / `user_id: UUID` en FastAPI ya llegan
  coaccionados — **no** volver a envolverlos.
- Cualquier valor que venga de un dict, de un `payload` de auditoría, de un query
  param sin tipar o de una comparación armada a mano: `uuid.UUID(str(valor))` antes
  de comparar.
- Las rutas nuevas del §4 declaran `user_id: UUID` en la firma. Esa es la única
  coerción necesaria; el resto del flujo trabaja con IDs internos `int`.

### 3.4 Invariante de creación

Un curso nuevo **nunca** puede quedar con `teacher_id` legacy poblado y sin fila en
`lms_course_teachers`. En `create_course`, inmediatamente después del
`CourseRepository.create(...)`:

```python
if teacher_id is not None:
    CourseTeacherRepository(session).add(course.id, teacher_id)
```

### 3.5 Invariante de remoción

`DELETE` que dejaría el curso con **cero** docentes → `400` con mensaje explícito.
Ningún curso activo queda sin docente. (Consistente con el flujo actual, donde
`CourseCreateBody.teacher_id` es obligatorio: todo curso nace con uno.)

---

## 4. Contrato de API

Cambio **rompiente y deliberado**: no se mantiene el campo singular. Dejar
`teacher` (¿cuál de N?) junto a `teachers` es deuda disfrazada de compatibilidad, y
el frontend se actualiza en el mismo PR — no hay consumidor externo que proteger.

### 4.1 `GET /academic/courses/{course_id}` → `CourseDetail`

```json
{
  "public_id": "3f1c0e2a-1c4e-4f1a-9b2d-000000000001",
  "name": "Robótica 5A",
  "description": "Curso de robótica para quinto",
  "is_active": true,
  "created_at": "2026-07-01T14:20:00Z",
  "updated_at": "2026-07-20T09:05:00Z",
  "teachers": [
    {
      "public_id": "aa11bb22-0000-4000-8000-000000000010",
      "first_name": "Ana María",
      "last_name": "Rojas",
      "email": "ana.rojas@ejemplo.edu.co",
      "is_active": true
    },
    {
      "public_id": "aa11bb22-0000-4000-8000-000000000011",
      "first_name": "Jose",
      "last_name": "Molina",
      "email": "academica@ejemplo.edu.co",
      "is_active": true
    }
  ],
  "students": [],
  "units": []
}
```

- `teachers` ordenado por `first_name, last_name`.
- Puede venir **vacío** (`[]`) solo si la columna legacy quedó nula en datos viejos;
  el frontend renderiza `—`, no asume `[0]`.
- Los objetos de `teachers` son `UserRead` completos, mismo shape que `students`.

### 4.2 `GET /academic/my-courses` → `list[MyCourseRead]`

```json
[
  {
    "public_id": "3f1c0e2a-1c4e-4f1a-9b2d-000000000001",
    "name": "Robótica 5A",
    "description": null,
    "is_active": true,
    "created_at": "2026-07-01T14:20:00Z",
    "updated_at": "2026-07-20T09:05:00Z",
    "grade_name": "Quinto",
    "school_name": "Gimnasio Nueva Escocia",
    "teacher_names": ["Ana María Rojas", "Jose Molina"],
    "role": "TEACHER"
  }
]
```

`role` sigue siendo `TEACHER` cuando el curso viene de `get_my_courses_as_teacher`
(que ahora resuelve por la tabla puente); sin cambios de semántica.

### 4.3 `POST /academic/courses/{course_id}/teachers` — **agrega** (no reemplaza)

- Auth: **ADMIN únicamente** (`Depends(require_roles("ADMIN"))`)
- Body: `{"teacher_id": "<uuid del usuario>"}`
- Respuesta: `204 No Content`
- Idempotente: agregar dos veces el mismo docente devuelve `204` sin duplicar.

| Código | Cuándo |
|---|---|
| 204 | agregado (o ya estaba) |
| 403 | el solicitante no es ADMIN |
| 404 | curso o docente inexistente |
| 400 | el usuario no tiene rol `TEACHER` ni es director del grado |

### 4.4 `DELETE /academic/courses/{course_id}/teachers/{user_id}` — quita

- Auth: **ADMIN únicamente**
- `user_id` es el `public_id` del usuario, tipado `UUID` en la firma
- Respuesta: `204 No Content`

| Código | Cuándo |
|---|---|
| 204 | removido |
| 400 | dejaría el curso con cero docentes (§3.5) |
| 403 | el solicitante no es ADMIN |
| 404 | curso o docente inexistente, o el usuario no era docente del curso |

### 4.5 `GET /academic/courses/{course_id}/assignable-teachers`

Sin cambio de shape (`list[UserRead]` con `roles`). Cambia el criterio: excluye a
**todos** los docentes ya asignados, no solo al único actual.

### 4.6 Rutas eliminadas

`POST /academic/courses/{course_id}/teacher` (singular) — se borra del router, sin
alias muerto.

### 4.7 Decisión de permisos que hay que confirmar antes de mergear

**El endurecimiento a ADMIN-only deja una inconsistencia visible:**
`GET .../assignable-teachers` sigue siendo `ADMIN, DIRECTOR` (`routes/courses.py:109`),
y `POST .../courses` (crear curso con docente) también (`routes/grades.py:157`). O sea,
un DIRECTOR podrá **crear** un curso eligiendo docente y **listar** candidatos, pero
no podrá agregar un segundo docente ni quitar uno.

El ADR lo pide explícitamente ADMIN-only y así se implementa, pero es un cambio de
comportamiento para directores que hoy sí asignan. **Manager: confirmar con producto
antes del merge.** Si producto dice que el DIRECTOR del grado debe poder gestionar
docentes de sus cursos, el cambio es de una línea (`require_roles("ADMIN", "DIRECTOR")`
+ `_assert_admin_or_director` dentro del service) y conviene decidirlo antes de que el
frontend gatee los botones por rol.

---

## 5. Orden de ejecución

| Paso | Responsable | Depende de | Entregable |
|---|---|---|---|
| 1 | `coder-migracion-modelo` | — | Modelo + migración (§1). Correr up/down contra copia con datos reales; conteo pre/post debe cuadrar. |
| 2 | `coder-backend` | 1 | Repo nuevo, service, rutas, schemas, puente `users-sync`, tests (§2.2-2.9, §3) |
| 3 | `coder-frontend` | 1 (contrato §4 congelado) | Los 7 archivos de §2.10 |
| 4 | `reviewer-permisos` | 1,2,3 | Grep de §3.1 vacío; 403 para DIRECTOR/TEACHER en POST/DELETE; co-docente califica; docente removido pierde acceso; downgrade aborta limpio con multi-docente; coerción UUID verificada contra el código, no contra el PR |
