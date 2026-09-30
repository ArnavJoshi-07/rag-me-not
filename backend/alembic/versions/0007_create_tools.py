"""create tools

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-30 21:10:06.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tools",
        sa.Column("tool_id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tool_type", sa.Text(), nullable=False, comment="rag / mcp / sandbox"),
        sa.Column("name", sa.Text(), nullable=False, comment="rag.search / mcp.<server>.<tool> / sandbox.<action>"),
        sa.Column("description", sa.Text(), server_default="", nullable=False, comment="Passed to the LLM"),
        sa.Column(
            "input_schema",
            postgresql.JSONB(),
            nullable=False,
            comment="JSON schema, passed to LiteLLM as the tool definition",
        ),
        sa.Column(
            "parallel_safe",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
            comment="rag -> true, sandbox -> false, mcp -> from the tool's readOnlyHint annotation, admin can override",
        ),
        sa.Column("mcp_server_id", sa.Uuid(), nullable=True, comment="Only for tool_type = mcp"),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("tool_id", name="pk_tools"),
        sa.ForeignKeyConstraint(
            ["mcp_server_id"],
            ["mcp_servers.mcp_server_id"],
            name="fk_tools_mcp_server_id_mcp_servers",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("name", name="uq_tools_name"),
        sa.CheckConstraint("tool_type IN ('rag', 'mcp', 'sandbox')", name="ck_tools_tool_type"),
        sa.CheckConstraint("starts_with(name, tool_type || '.')", name="ck_tools_name_prefix"),
        sa.CheckConstraint("(tool_type = 'mcp') = (mcp_server_id IS NOT NULL)", name="ck_tools_mcp_server_id"),
        sa.CheckConstraint("jsonb_typeof(input_schema) = 'object'", name="ck_tools_input_schema_object"),
        comment=(
            "Every tool an agent can be given. rag + sandbox rows are added by a migration, "
            "mcp rows are filled from each server's tools/list"
        ),
    )
    op.create_index("ix_tools_mcp_server_id", "tools", ["mcp_server_id"])
    op.execute(
        "CREATE TRIGGER trg_tools_set_updated_at BEFORE UPDATE ON tools "
        "FOR EACH ROW WHEN (OLD.* IS DISTINCT FROM NEW.*) EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    op.drop_table("tools")
