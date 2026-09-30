"""create agent_connectors

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-30 21:10:09.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_connectors",
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("connector_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("agent_id", "connector_id", name="pk_agent_connectors"),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agents.agent_id"], name="fk_agent_connectors_agent_id_agents", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["connector_id"],
            ["connectors.connector_id"],
            name="fk_agent_connectors_connector_id_connectors",
            ondelete="CASCADE",
        ),
        comment=(
            "Connectors the agent's rag tool may search (many-to-many). Always applied as a connector_id filter, "
            "the LLM can only narrow it"
        ),
    )
    # the primary key covers agent_id lookups, this covers "which agents search this connector" and the FK cascade
    op.create_index("ix_agent_connectors_connector_id", "agent_connectors", ["connector_id"])


def downgrade() -> None:
    op.drop_table("agent_connectors")
