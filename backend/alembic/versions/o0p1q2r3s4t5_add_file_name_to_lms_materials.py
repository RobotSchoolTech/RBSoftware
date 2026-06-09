"""add_file_name_to_lms_materials

Revision ID: o0p1q2r3s4t5
Revises: n9o0p1q2r3s4
Create Date: 2026-06-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'o0p1q2r3s4t5'
down_revision = 'n9o0p1q2r3s4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nombre original del archivo, necesario para materiales tomados del
    # repositorio (detección de tipo en el visor + descarga con nombre real).
    op.add_column(
        'lms_materials',
        sa.Column('file_name', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('lms_materials', 'file_name')
