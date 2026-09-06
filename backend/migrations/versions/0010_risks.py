"""Add enterprise risk management table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0010_risks"
down_revision: Union[str, Sequence[str], None] = "0009_idempotency_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "risks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("risk_key", sa.String(80), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("impact", sa.String(30), nullable=False, server_default="MEDIUM"),
        sa.Column("likelihood", sa.String(30), nullable=False, server_default="MEDIUM"),
        sa.Column("status", sa.String(30), nullable=False, server_default="OPEN"),
        sa.Column("category", sa.String(50), nullable=False, server_default="TECHNICAL"),
        sa.Column("mitigation_strategy", sa.Text(), nullable=True),
        sa.Column("contingency_plan", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(200), nullable=True),
        sa.Column("severity_score", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("associated_requirement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("requirements.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_risks_tenant_status", "risks", ["tenant_id", "status"])
    op.create_index("ix_risks_tenant_impact", "risks", ["tenant_id", "impact"])
    op.create_index("ix_risks_tenant_project", "risks", ["tenant_id", "project_id"])


def downgrade() -> None:
    op.drop_index("ix_risks_tenant_project", table_name="risks")
    op.drop_index("ix_risks_tenant_impact", table_name="risks")
    op.drop_index("ix_risks_tenant_status", table_name="risks")
    op.drop_table("risks")
