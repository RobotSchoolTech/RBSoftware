"""expand_work_line_enum

Agrega los valores kuntur_abierto, ecua_2, ecua_3 y ares al enum work_line.
Afecta las dos columnas que lo usan: schools.work_line y
repository_folder_shares.work_line. En MySQL el ENUM es inline en cada columna,
así que se expande con ALTER TABLE ... MODIFY COLUMN en ambas.

Revision ID: q2r3s4t5u6v7
Revises: p1q2r3s4t5u6
Create Date: 2026-07-08 00:00:00.000000

"""
from alembic import op


revision = 'q2r3s4t5u6v7'
down_revision = 'p1q2r3s4t5u6'
branch_labels = None
depends_on = None


NEW_ENUM = (
    "ENUM('kuntur','kuntur_abierto','ecua','ecua_2','ecua_3','ares','robotschool')"
)
OLD_ENUM = "ENUM('kuntur','ecua','robotschool')"


def upgrade() -> None:
    op.execute(f"ALTER TABLE schools MODIFY COLUMN work_line {NEW_ENUM} NULL")
    op.execute(
        f"ALTER TABLE repository_folder_shares MODIFY COLUMN work_line {NEW_ENUM} NULL"
    )


def downgrade() -> None:
    # Revierte al enum de 3 valores. Falla si existen filas con los valores nuevos.
    op.execute(
        f"ALTER TABLE repository_folder_shares MODIFY COLUMN work_line {OLD_ENUM} NULL"
    )
    op.execute(f"ALTER TABLE schools MODIFY COLUMN work_line {OLD_ENUM} NULL")
