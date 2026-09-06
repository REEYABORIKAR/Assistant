"""Add append-only audit event storage."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_audit_events"
down_revision: Union[str, Sequence[str], None] = "0001_auth_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT")),
        sa.Column("event_type", postgresql.CITEXT(), nullable=False),
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True)),
        sa.Column("resource_type", sa.String(60)),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True)),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("request_id", sa.String(80)),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sessions.id", ondelete="SET NULL")),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("event_type = upper(event_type)", name="ck_audit_events_event_type_upper"),
        sa.CheckConstraint("outcome IN ('SUCCEEDED','DENIED','FAILED')", name="ck_audit_events_outcome"),
        sa.Index("ix_audit_events_tenant_created", "tenant_id", "created_at"),
        sa.Index("ix_audit_events_actor_created", "actor_id", "created_at"),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
