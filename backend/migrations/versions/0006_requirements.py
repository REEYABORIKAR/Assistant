"""Add project-scoped requirements."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0006_requirements"
down_revision: Union[str, Sequence[str], None] = "0005_files"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "requirements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requirement_key", postgresql.CITEXT(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
        sa.Column("source_type", sa.String(40), nullable=False, server_default="UNVERIFIED"),
        sa.Column("source_id", postgresql.UUID(as_uuid=True)),
        sa.Column("source_location", sa.String(200)),
        sa.Column("confidence", sa.Numeric(4, 3)),
        sa.Column("missing_information", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "project_id", "requirement_key", "version", name="uq_requirements_key_version"),
        sa.CheckConstraint("version >= 1", name="ck_requirements_version_positive"),
        sa.CheckConstraint("confidence IS NULL OR confidence BETWEEN 0 AND 1", name="ck_requirements_confidence"),
    )
    op.create_index("ix_requirements_project_type_status", "requirements", ["project_id", "type", "status"])
    op.create_index("ix_requirements_project_key", "requirements", ["project_id", "requirement_key"])


def downgrade() -> None:
    op.drop_index("ix_requirements_project_key", table_name="requirements")
    op.drop_index("ix_requirements_project_type_status", table_name="requirements")
    op.drop_table("requirements")
