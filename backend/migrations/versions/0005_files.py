"""Add file ingestion metadata."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0005_files"
down_revision: Union[str, Sequence[str], None] = "0004_conversations_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(200), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.LargeBinary(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="UPLOADING"),
        sa.Column("scan_result", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("scanned_at", sa.DateTime(timezone=True)),
        sa.Column("scanner_name", sa.String(100)),
        sa.Column("quarantined_at", sa.DateTime(timezone=True)),
        sa.Column("quarantine_reason", sa.Text()),
        sa.Column("extraction_error", sa.Text()),
        sa.Column("page_count", sa.Integer()),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("size_bytes > 0", name="ck_files_size_positive"),
    )
    op.create_index("ix_files_tenant_project_status", "files", ["tenant_id", "project_id", "status"])
    op.create_index("ix_files_tenant_checksum", "files", ["tenant_id", "checksum_sha256"])


def downgrade() -> None:
    op.drop_index("ix_files_tenant_checksum", table_name="files")
    op.drop_index("ix_files_tenant_project_status", table_name="files")
    op.drop_table("files")
