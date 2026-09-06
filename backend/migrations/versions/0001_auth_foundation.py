"""Create the initial authentication and tenant foundation tables."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_auth_foundation"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    for name, values in {
        "tenant_status": ("ACTIVE", "SUSPENDED", "DELETED"),
        "user_status": ("PENDING", "ACTIVE", "DISABLED", "LOCKED"),
        "membership_status": ("INVITED", "ACTIVE", "SUSPENDED", "REMOVED"),
        "consent_kind": ("TERMS_OF_SERVICE", "PRIVACY_POLICY", "DATA_PROCESSING"),
    }.items():
        labels = ", ".join(f"'{value}'" for value in values)
        op.execute(sa.text(f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({labels}); EXCEPTION WHEN duplicate_object THEN NULL; END $$;"))

    uuid_type = postgresql.UUID(as_uuid=True)
    now = sa.text("now()")
    op.create_table(
        "tenants",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", postgresql.CITEXT(), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", postgresql.ENUM(name="tenant_status", create_type=False), nullable=False, server_default="ACTIVE"),
        sa.Column("settings", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_table(
        "users",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", postgresql.CITEXT(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", postgresql.ENUM(name="user_status", create_type=False), nullable=False, server_default="PENDING"),
        sa.Column("email_verified_at", sa.DateTime(timezone=True)),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_table(
        "tenant_members",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", uuid_type, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", postgresql.ENUM(name="membership_status", create_type=False), nullable=False, server_default="INVITED"),
        sa.Column("invited_by", uuid_type, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("joined_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.UniqueConstraint("tenant_id", "user_id"),
    )
    op.create_table(
        "sessions",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", uuid_type, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_reason", sa.String(60)),
        sa.Column("ip_address", postgresql.INET()),
        sa.Column("user_agent", sa.Text()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Index("ix_sessions_user_revoked", "user_id", "revoked_at"),
        sa.Index("ix_sessions_expires_at", "expires_at"),
        sa.Index("ix_sessions_tenant_id", "tenant_id"),
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", uuid_type, sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("replaced_by", uuid_type, sa.ForeignKey("refresh_tokens.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Index("ix_refresh_tokens_session_id", "session_id"),
        sa.Index("ix_refresh_tokens_expires_at", "expires_at"),
    )
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("requested_ip", postgresql.INET()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Index("ix_password_reset_tokens_user_id", "user_id"),
        sa.Index("ix_password_reset_tokens_expires_at", "expires_at"),
    )
    op.create_table(
        "consents",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("consent_kind", postgresql.ENUM(name="consent_kind", create_type=False), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("ip_address", postgresql.INET()),
        sa.Column("user_agent", sa.Text()),
        sa.UniqueConstraint("user_id", "consent_kind", "policy_version"),
        sa.Index("ix_consents_user_id", "user_id"),
    )


def downgrade() -> None:
    for table in ("consents", "password_reset_tokens", "refresh_tokens", "sessions", "tenant_members", "users", "tenants"):
        op.drop_table(table)
    for name in ("consent_kind", "membership_status", "user_status", "tenant_status"):
        op.execute(sa.text(f"DROP TYPE IF EXISTS {name}"))
