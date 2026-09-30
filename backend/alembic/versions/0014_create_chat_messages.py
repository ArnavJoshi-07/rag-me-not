"""create chat_messages

Also adds touch_chat_session(): every inserted message moves its session's
updated_at forward, which keeps the chat sidebar sorted by latest message.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-30 21:10:13.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column("message_id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("chat_session_id", sa.Uuid(), nullable=False),
        sa.Column(
            "agent_id",
            sa.Uuid(),
            nullable=True,
            comment="Agent chosen for this message, can change per message",
        ),
        sa.Column("message", sa.Text(), server_default="", nullable=False),
        sa.Column("message_type", sa.Text(), nullable=False, comment="system / user / assistant"),
        sa.Column("parent_message_id", sa.Uuid(), nullable=True, comment="Latest user input"),
        sa.Column("child_message_id", sa.Uuid(), nullable=True, comment="LLM response to the latest user input"),
        sa.Column(
            "message_tokens",
            sa.Integer(),
            nullable=True,
            comment="assistant -> thinking + generation tokens, user -> input tokens, system -> system prompt tokens",
        ),
        sa.Column(
            "citations",
            postgresql.JSONB(),
            nullable=True,
            comment="Citations used to generate the response, assistant messages only",
        ),
        sa.Column(
            "status",
            sa.Text(),
            server_default="complete",
            nullable=False,
            comment="streaming / complete / error. Only assistant messages are streaming / error",
        ),
        sa.Column(
            "error",
            sa.Text(),
            nullable=True,
            comment="Why generation failed or stopped (provider error, timeout, user cancelled)",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "generation_time", sa.Integer(), nullable=True, comment="Time to generate the response, in milliseconds"
        ),
        sa.Column(
            "model_id",
            sa.Uuid(),
            nullable=True,
            comment="Model the request was sent to / answer generated from",
        ),
        sa.Column(
            "model_name",
            sa.Text(),
            nullable=True,
            comment="Copy of llm_models.model_name when the message is saved, still shown after the model is deleted",
        ),
        sa.PrimaryKeyConstraint("message_id", name="pk_chat_messages"),
        sa.ForeignKeyConstraint(
            ["chat_session_id"],
            ["chat_sessions.chat_session_id"],
            name="fk_chat_messages_chat_session_id_chat_sessions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agents.agent_id"], name="fk_chat_messages_agent_id_agents", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["parent_message_id"],
            ["chat_messages.message_id"],
            name="fk_chat_messages_parent_message_id_chat_messages",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["child_message_id"],
            ["chat_messages.message_id"],
            name="fk_chat_messages_child_message_id_chat_messages",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"], ["llm_models.model_id"], name="fk_chat_messages_model_id_llm_models", ondelete="SET NULL"
        ),
        sa.CheckConstraint("message_type IN ('system', 'user', 'assistant')", name="ck_chat_messages_message_type"),
        sa.CheckConstraint("status IN ('streaming', 'complete', 'error')", name="ck_chat_messages_status"),
        sa.CheckConstraint(
            "message_type = 'assistant' OR status = 'complete'", name="ck_chat_messages_status_assistant_only"
        ),
        sa.CheckConstraint(
            "message_type = 'assistant' OR citations IS NULL", name="ck_chat_messages_citations_assistant_only"
        ),
        sa.CheckConstraint("message_tokens >= 0", name="ck_chat_messages_message_tokens_non_negative"),
        sa.CheckConstraint("generation_time >= 0", name="ck_chat_messages_generation_time_non_negative"),
        comment="One row per message in a chat session",
    )
    # load a chat in order (also covers the chat_session_id FK cascade)
    op.create_index("ix_chat_messages_chat_session_id_created_at", "chat_messages", ["chat_session_id", "created_at"])
    # Postgres doesn't index FK columns on its own. without these, every deleted message / agent / model
    # scans chat_messages to find the rows to SET NULL
    op.create_index("ix_chat_messages_parent_message_id", "chat_messages", ["parent_message_id"])
    op.create_index("ix_chat_messages_child_message_id", "chat_messages", ["child_message_id"])
    op.create_index("ix_chat_messages_agent_id", "chat_messages", ["agent_id"])
    op.create_index("ix_chat_messages_model_id", "chat_messages", ["model_id"])

    op.execute(
        "CREATE TRIGGER trg_chat_messages_set_updated_at BEFORE UPDATE ON chat_messages "
        "FOR EACH ROW WHEN (OLD.* IS DISTINCT FROM NEW.*) EXECUTE FUNCTION set_updated_at()"
    )
    op.execute(
        """
        CREATE FUNCTION touch_chat_session() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            UPDATE chat_sessions
               SET updated_at = GREATEST(updated_at, NEW.created_at)
             WHERE chat_session_id = NEW.chat_session_id;
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER trg_chat_messages_touch_chat_session AFTER INSERT ON chat_messages "
        "FOR EACH ROW EXECUTE FUNCTION touch_chat_session()"
    )


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.execute("DROP FUNCTION touch_chat_session()")
