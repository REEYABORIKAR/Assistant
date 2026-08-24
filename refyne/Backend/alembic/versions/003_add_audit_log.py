"""Add audit_log table.

Revision ID: 003
Revises: 002_add_project_members
Create Date: 2026-08-21
"""
import sqlalchemy as sa

from alembic import op

# revision identifiers
revision = '003_add_audit_log'
down_revision = '002_add_project_members'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'audit_log',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=True),
        sa.Column('resource_id', sa.String(36), nullable=True),
        sa.Column('trace_id', sa.String(16), nullable=True),
        sa.Column('details', sa.Text, nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
    )
    op.create_index('ix_audit_log_timestamp', 'audit_log', ['timestamp'])
    op.create_index('ix_audit_log_user_id', 'audit_log', ['user_id'])
    op.create_index('ix_audit_log_project_id', 'audit_log', ['project_id'])
    op.create_index('ix_audit_log_action', 'audit_log', ['action'])


def downgrade() -> None:
    op.drop_table('audit_log')
