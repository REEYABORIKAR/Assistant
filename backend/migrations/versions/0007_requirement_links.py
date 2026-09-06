"""Add requirement traceability links."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0007_requirement_links"
down_revision: Union[str, Sequence[str], None] = "0006_requirements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "requirement_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_requirement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_requirement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("source_requirement_id", "target_requirement_id", "relationship", name="uq_requirement_links"),
        sa.CheckConstraint("source_requirement_id <> target_requirement_id", name="ck_requirement_links_distinct"),
    )
    op.create_index("ix_requirement_links_target", "requirement_links", ["target_requirement_id"])


def downgrade() -> None:
    op.drop_index("ix_requirement_links_target", table_name="requirement_links")
    op.drop_table("requirement_links")
