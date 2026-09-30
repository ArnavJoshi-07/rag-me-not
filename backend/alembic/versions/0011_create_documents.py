"""create documents

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-30 21:10:10.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("document_id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("connector_id", sa.Uuid(), nullable=False),
        sa.Column(
            "external_id",
            sa.Text(),
            nullable=False,
            comment="File's id in the source -> s3 key, gdrive file id, MinIO key for file connectors",
        ),
        sa.Column("file_name", sa.Text(), nullable=False, comment="Shown in citations"),
        sa.Column("url", sa.Text(), nullable=True, comment="Link to the file in the source, shown in citations"),
        sa.Column("mime_type", sa.Text(), nullable=True, comment="Picks the parser -> pdf, xlsx, pptx, txt, image"),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column(
            "source_version",
            sa.Text(),
            nullable=True,
            comment="Change marker the source gives without downloading -> s3 ETag, gdrive modifiedTime",
        ),
        sa.Column("content_hash", sa.Text(), nullable=True, comment="sha256 (hex) of the downloaded file bytes"),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False, comment="pending / indexed / failed"),
        sa.Column("error", sa.Text(), nullable=True, comment="Parse / embed error if failed"),
        sa.Column(
            "chunk_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
            comment="Chunks written to OpenSearch",
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Last sync that found this file in the source, used to detect files deleted at the source",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("document_id", name="pk_documents"),
        sa.ForeignKeyConstraint(
            ["connector_id"],
            ["connectors.connector_id"],
            name="fk_documents_connector_id_connectors",
            ondelete="CASCADE",
        ),
        # one row per file per connector, also serves as the index for connector_id lookups and the FK cascade
        sa.UniqueConstraint("connector_id", "external_id", name="uq_documents_connector_id_external_id"),
        sa.CheckConstraint("status IN ('pending', 'indexed', 'failed')", name="ck_documents_status"),
        sa.CheckConstraint("size_bytes >= 0", name="ck_documents_size_bytes_non_negative"),
        sa.CheckConstraint("chunk_count >= 0", name="ck_documents_chunk_count_non_negative"),
        sa.CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="ck_documents_content_hash_sha256"),
        comment=(
            "One row per file pulled by a connector. Chunks live in OpenSearch and store document_id + connector_id, "
            "they are deleted in code when a document / connector is deleted"
        ),
    )
    op.execute(
        "CREATE TRIGGER trg_documents_set_updated_at BEFORE UPDATE ON documents "
        "FOR EACH ROW WHEN (OLD.* IS DISTINCT FROM NEW.*) EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    op.drop_table("documents")
