"""create agent_events

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-30 21:10:15.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_events",
        sa.Column("event_id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False, comment="Assistant message this step belongs to"),
        sa.Column("round", sa.SmallInteger(), nullable=False, comment="Agent loop round (1-5)"),
        sa.Column("seq", sa.Integer(), nullable=False, comment="Order of the event within the message"),
        sa.Column("event_type", sa.Text(), nullable=False, comment="analysis / tool_call / tool_result / reflection"),
        sa.Column(
            "tool_name",
            sa.Text(),
            nullable=True,
            comment="Tool events only. Plain text, not an FK, so the timeline survives a deleted tool",
        ),
        sa.Column("call_id", sa.Text(), nullable=True, comment="Links a tool_call to its tool_result"),
        sa.Column("status", sa.Text(), nullable=True, comment="ok / error, tool_result only"),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment="Analysis output, tool args + reason, result content + citations, reflection text",
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=True, comment="Time taken by the step"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("event_id", name="pk_agent_events"),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["chat_messages.message_id"],
            name="fk_agent_events_message_id_chat_messages",
            ondelete="CASCADE",
        ),
        # loads a timeline in order, and stops the same step being saved twice (also covers the FK cascade)
        sa.UniqueConstraint("message_id", "round", "seq", name="uq_agent_events_message_id_round_seq"),
        sa.CheckConstraint(
            "event_type IN ('analysis', 'tool_call', 'tool_result', 'reflection')", name="ck_agent_events_event_type"
        ),
        sa.CheckConstraint("round >= 1", name="ck_agent_events_round_positive"),
        sa.CheckConstraint("seq >= 0", name="ck_agent_events_seq_non_negative"),
        sa.CheckConstraint(
            "tool_name IS NULL OR event_type IN ('tool_call', 'tool_result')",
            name="ck_agent_events_tool_name_tool_only",
        ),
        sa.CheckConstraint(
            "call_id IS NULL OR event_type IN ('tool_call', 'tool_result')", name="ck_agent_events_call_id_tool_only"
        ),
        sa.CheckConstraint("status IN ('ok', 'error')", name="ck_agent_events_status"),
        sa.CheckConstraint(
            "status IS NULL OR event_type = 'tool_result'", name="ck_agent_events_status_tool_result_only"
        ),
        sa.CheckConstraint("duration_ms >= 0", name="ck_agent_events_duration_ms_non_negative"),
        comment=(
            "Agent loop timeline, one row per step. Shown in the chat timeline, never fed back to the LLM as history"
        ),
    )


def downgrade() -> None:
    op.drop_table("agent_events")
