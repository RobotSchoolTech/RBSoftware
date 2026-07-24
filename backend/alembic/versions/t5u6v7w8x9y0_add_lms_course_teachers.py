"""add_lms_course_teachers

Revision ID: t5u6v7w8x9y0
Revises: s4t5u6v7w8x9
Create Date: 2026-07-24 00:00:00.000000

Expand/contract: crea la tabla puente lms_course_teachers (co-dictado),
copia cada teacher_id existente de lms_courses (ningun curso con docente
queda huerfano) y vuelve lms_courses.teacher_id NULLABLE. NO se borra la
columna legacy en esta migracion (contract queda para un PR futuro una vez
confirmado que nada mas la lee).

Verificacion de integridad (correr a mano antes/despues de aplicar, o via
`alembic upgrade head` seguido de las dos queries de abajo en la BD real):

    SELECT COUNT(*) FROM lms_courses WHERE teacher_id IS NOT NULL;      -- PRE
    SELECT COUNT(*) FROM lms_course_teachers;                          -- POST

Ambos conteos deben coincidir 1:1 tras el upgrade.
"""
from alembic import op
import sqlalchemy as sa


revision = 't5u6v7w8x9y0'
down_revision = 's4t5u6v7w8x9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lms_course_teachers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "course_id",
            sa.Integer(),
            sa.ForeignKey("lms_courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("course_id", "user_id", name="uq_lms_course_teachers_course_user"),
    )

    conn = op.get_bind()

    # Conteo PRE: cursos con docente asignado hoy.
    pre_count = conn.execute(
        sa.text("SELECT COUNT(*) FROM lms_courses WHERE teacher_id IS NOT NULL")
    ).scalar_one()

    # Copia de datos: un curso con teacher_id no-nulo obtiene su fila puente.
    conn.execute(
        sa.text(
            """
            INSERT INTO lms_course_teachers (course_id, user_id, created_at)
            SELECT id, teacher_id, NOW()
            FROM lms_courses
            WHERE teacher_id IS NOT NULL
            """
        )
    )

    # Conteo POST: debe coincidir 1:1 con el PRE (ningun curso con docente
    # queda huerfano). UNIQUE(course_id, user_id) ya garantiza que no hay
    # duplicados por curso, así que un COUNT igual implica una fila por curso.
    post_count = conn.execute(
        sa.text("SELECT COUNT(*) FROM lms_course_teachers")
    ).scalar_one()

    if post_count != pre_count:
        raise RuntimeError(
            f"Migracion abortada: {pre_count} curso(s) con teacher_id no-nulo "
            f"pero solo se copiaron {post_count} fila(s) a lms_course_teachers. "
            "Ningun curso con docente puede quedar huerfano."
        )

    # teacher_id pasa a NULLABLE. NO se borra la columna en este PR.
    op.alter_column(
        "lms_courses",
        "teacher_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Si algun curso quedo con mas de un docente tras el upgrade, el downgrade
    # no puede reconstruir teacher_id sin decidir arbitrariamente cual --
    # se aborta explicitamente en vez de truncar datos en silencio.
    multi = conn.execute(
        sa.text(
            "SELECT course_id FROM lms_course_teachers GROUP BY course_id HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if multi:
        raise RuntimeError(
            f"Downgrade abortado: {len(multi)} curso(s) tienen mas de un docente "
            "asignado; resolver a mano antes de bajar la migracion."
        )

    # Repoblar teacher_id ANTES de forzar NOT NULL: si se invierte el orden,
    # cualquier curso creado despues del upgrade con teacher_id NULL revienta
    # el ALTER con IntegrityError.
    conn.execute(
        sa.text(
            """
            UPDATE lms_courses c
            JOIN lms_course_teachers ct ON ct.course_id = c.id
            SET c.teacher_id = ct.user_id
            """
        )
    )

    # Validar que no quedan huerfanos (curso activo en lms_course_teachers
    # sin fila, o teacher_id todavia NULL) antes de endurecer la columna.
    orphans = conn.execute(
        sa.text("SELECT COUNT(*) FROM lms_courses WHERE teacher_id IS NULL")
    ).scalar_one()
    if orphans:
        raise RuntimeError(
            f"Downgrade abortado: {orphans} curso(s) quedarian con teacher_id "
            "NULL (sin fila en lms_course_teachers); resolver a mano antes de "
            "bajar la migracion."
        )

    op.alter_column(
        "lms_courses",
        "teacher_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_table("lms_course_teachers")
