"""create chat_files

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-30 21:10:14.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_files",
        sa.Column("chat_file_id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("chat_session_id", sa.Uuid(), nullable=False, comment="Chat the file was uploaded in"),
        sa.Column(
            "message_id",
            sa.Uuid(),
            nullable=True,
            comment="User message the file is attached to. NULL while uploaded but not sent yet",
        ),
        sa.Column("file_name", sa.Text(), nullable=False, comment="Original file name"),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column(
            "storage_path",
            sa.Text(),
            nullable=False,
            comment="MinIO object key -> chat-uploads/<chat_session_id>/<chat_file_id>",
        ),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("chat_file_id", name="pk_chat_files"),
        sa.ForeignKeyConstraint(
            ["chat_session_id"],
            ["chat_sessions.chat_session_id"],
            name="fk_chat_files_chat_session_id_chat_sessions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["chat_messages.message_id"],
            name="fk_chat_files_message_id_chat_messages",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("storage_path", name="uq_chat_files_storage_path"),
        sa.CheckConstraint("size_bytes >= 0", name="ck_chat_files_size_bytes_non_negative"),
        comment="Metadata of files uploaded in a chat, the bytes live in MinIO and are deleted in code",
    )
    op.create_index("ix_chat_files_chat_session_id", "chat_files", ["chat_session_id"])
    op.create_index("ix_chat_files_message_id", "chat_files", ["message_id"])


def downgrade() -> None:
    op.drop_table("chat_files")
