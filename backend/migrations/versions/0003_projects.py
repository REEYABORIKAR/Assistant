"""Add tenant-scoped projects."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_projects"
down_revision: Union[str, Sequence[str], None] = "0002_audit_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("project_key", postgresql.CITEXT(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "project_key", name="uq_projects_tenant_project_key"),
        sa.CheckConstraint("status IN ('ACTIVE','ARCHIVED')", name="ck_projects_status"),
    )
    op.create_index("ix_projects_tenant_status", "projects", ["tenant_id", "status"])
    op.create_index("ix_projects_tenant_name", "projects", ["tenant_id", "name"])


def downgrade() -> None:
    op.drop_index("ix_projects_tenant_name", table_name="projects")
    op.drop_index("ix_projects_tenant_status", table_name="projects")
    op.drop_table("projects")
