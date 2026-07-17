"""add_logro_to_lms_assignments

Revision ID: s4t5u6v7w8x9
Revises: r3s4t5u6v7w8
Create Date: 2026-07-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 's4t5u6v7w8x9'
down_revision = 'r3s4t5u6v7w8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'lms_assignments',
        sa.Column(
            'logro',
            sa.Enum('disenar', 'programar', 'robotizar', name='logro'),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # En MySQL el ENUM es inline en la columna: drop_column lo elimina.
    # No hay `DROP TYPE` (eso es sintaxis PostgreSQL y rompería el downgrade en MySQL).
    op.drop_column('lms_assignments', 'logro')
