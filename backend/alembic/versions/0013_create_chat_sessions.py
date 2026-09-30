"""create chat_sessions

updated_at here is not bumped by set_updated_at(): it is the time of the latest
message, set by a trigger on chat_messages (next migration), so renaming a chat
does not move it to the top of the sidebar.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-30 21:10:12.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column(
            "chat_session_id",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="Also the thread_id for the whole conversation",
        ),
        sa.Column("chat_title", sa.Text(), nullable=True, comment="Condensed title from the first user message"),
        sa.Column(
            "agent_id",
            sa.Uuid(),
            nullable=True,
            comment="Agent the chat was created with, default for the next message",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Time of the latest message (set by a trigger on chat_messages), sorts the sidebar",
        ),
        sa.PrimaryKeyConstraint("chat_session_id", name="pk_chat_sessions"),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agents.agent_id"], name="fk_chat_sessions_agent_id_agents", ondelete="SET NULL"
        ),
        comment=(
            "One row per conversation, shown in the chat sidebar. Deleting one cascades to its messages, "
            "their agent_events and chat_files. Its MinIO files are deleted in code"
        ),
    )
    op.create_index("ix_chat_sessions_updated_at", "chat_sessions", ["updated_at"])
    op.create_index("ix_chat_sessions_agent_id", "chat_sessions", ["agent_id"])


def downgrade() -> None:
    op.drop_table("chat_sessions")
