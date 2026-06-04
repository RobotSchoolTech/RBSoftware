"""add_work_line_to_schools

Revision ID: m8n9o0p1q2r3
Revises: l7m8n9o0p1q2
Create Date: 2026-06-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'm8n9o0p1q2r3'
down_revision = 'dc94de4295fe'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'schools',
        sa.Column(
            'work_line',
            sa.Enum('kuntur', 'ecua', 'robotschool', name='workline'),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # En MySQL el tipo ENUM es inline en la columna: drop_column lo elimina.
    # No hay `DROP TYPE` (eso es sintaxis PostgreSQL y rompería el downgrade en MySQL).
    op.drop_column('schools', 'work_line')
