"""create agent_tools

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-30 21:10:07.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_tools",
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("tool_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("agent_id", "tool_id", name="pk_agent_tools"),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agents.agent_id"], name="fk_agent_tools_agent_id_agents", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tool_id"], ["tools.tool_id"], name="fk_agent_tools_tool_id_tools", ondelete="CASCADE"
        ),
        comment="Tools an agent can call (many-to-many)",
    )
    # the primary key covers agent_id lookups, this covers "which agents use this tool" and the FK cascade
    op.create_index("ix_agent_tools_tool_id", "agent_tools", ["tool_id"])


def downgrade() -> None:
    op.drop_table("agent_tools")
