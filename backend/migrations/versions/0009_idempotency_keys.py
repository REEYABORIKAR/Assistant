"""0009_idempotency_keys

Revision ID: 0009_idempotency_keys
Revises: 0008_workflow_definitions
Create Date: 2026-08-27 01:24:47.612000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0009_idempotency_keys"
down_revision: Union[str, Sequence[str], None] = "0008_workflow_definitions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_idempotency_key_tenant_endpoint_session",
        "idempotency_keys",
        ["tenant_id", "idempotency_key", "endpoint", "session_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_idempotency_key_tenant_endpoint_session", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
