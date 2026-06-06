"""add_repository_folder_shares

Revision ID: n9o0p1q2r3s4
Revises: m8n9o0p1q2r3
Create Date: 2026-06-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'n9o0p1q2r3s4'
down_revision = 'm8n9o0p1q2r3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'repository_folder_shares',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('folder_id', sa.Integer(), nullable=False),
        sa.Column(
            'scope_type',
            sa.Enum('work_line', 'school', name='sharescopetype'),
            nullable=False,
        ),
        sa.Column(
            'work_line',
            sa.Enum('kuntur', 'ecua', 'robotschool', name='workline'),
            nullable=True,
        ),
        sa.Column('school_id', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['folder_id'], ['repository_folders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'folder_id', 'scope_type', 'work_line', 'school_id',
            name='uq_repository_folder_shares_scope',
        ),
    )


def downgrade() -> None:
    op.drop_table('repository_folder_shares')
