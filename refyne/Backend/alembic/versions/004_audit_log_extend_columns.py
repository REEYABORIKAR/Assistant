"""Extend audit_log with model, versioning, and traceability columns.

Revision ID: 004
Revises: 003_add_audit_log
Create Date: 2026-08-22
"""
import sqlalchemy as sa

from alembic import op

revision = '004_audit_log_extend'
down_revision = '003_add_audit_log'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('audit_log', sa.Column('tenant_id', sa.String(36), nullable=True))
    op.add_column('audit_log', sa.Column('model', sa.String(100), nullable=True))
    op.add_column('audit_log', sa.Column('model_version', sa.String(50), nullable=True))
    op.add_column('audit_log', sa.Column('prompt_version', sa.String(50), nullable=True))
    op.add_column('audit_log', sa.Column('ip_address', sa.String(45), nullable=True))
    op.add_column('audit_log', sa.Column('old_value', sa.Text, nullable=True))
    op.add_column('audit_log', sa.Column('new_value', sa.Text, nullable=True))
    op.create_index('ix_audit_log_tenant_id', 'audit_log', ['tenant_id'])


def downgrade() -> None:
    op.drop_index('ix_audit_log_tenant_id', 'audit_log')
    op.drop_column('audit_log', 'new_value')
    op.drop_column('audit_log', 'old_value')
    op.drop_column('audit_log', 'ip_address')
    op.drop_column('audit_log', 'prompt_version')
    op.drop_column('audit_log', 'model_version')
    op.drop_column('audit_log', 'model')
    op.drop_column('audit_log', 'tenant_id')
