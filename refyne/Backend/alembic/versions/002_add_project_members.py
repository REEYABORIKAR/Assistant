"""add project_members table

Revision ID: 002
Revises: 001
Create Date: 2026-08-20

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '002'
down_revision: str | None = '001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'project_members',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, server_default='VIEWER'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('project_id', 'user_id', name='uq_project_user'),
    )
    op.create_index('ix_project_members_project_id', 'project_members', ['project_id'])
    op.create_index('ix_project_members_user_id', 'project_members', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_project_members_user_id')
    op.drop_index('ix_project_members_project_id')
    op.drop_table('project_members')
