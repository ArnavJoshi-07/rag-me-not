"""create mcp_servers

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-30 21:10:05.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_servers",
        sa.Column("mcp_server_id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column(
            "mcp_server_name",
            sa.Text(),
            nullable=False,
            comment="Unique slug, used in tool names -> mcp.<server>.<tool>",
        ),
        sa.Column(
            "transport",
            sa.Text(),
            nullable=False,
            comment="stdio / streamable_http / sse (sse only for older servers without streamable_http)",
        ),
        sa.Column("server_url", sa.Text(), nullable=True, comment="Remote only (streamable_http / sse)"),
        sa.Column(
            "headers",
            sa.Text(),
            nullable=True,
            comment="Remote only. Fernet-encrypted JSON of auth headers, never returned by the API",
        ),
        sa.Column("command", sa.Text(), nullable=True, comment="stdio only, executable to launch -> npx, uvx, docker"),
        sa.Column("args", postgresql.ARRAY(sa.Text()), nullable=True, comment="stdio only, list of arguments"),
        sa.Column(
            "env",
            sa.Text(),
            nullable=True,
            comment="stdio only. Fernet-encrypted JSON of env vars for the process, never returned by the API",
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
            comment="Tools of a disabled server are not offered to any agent",
        ),
        sa.Column(
            "tools_synced_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last time tools/list was pulled into the tools table",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("mcp_server_id", name="pk_mcp_servers"),
        sa.UniqueConstraint("mcp_server_name", name="uq_mcp_servers_mcp_server_name"),
        # no dots, they separate the parts of mcp.<server>.<tool>
        sa.CheckConstraint("mcp_server_name ~ '^[a-z0-9][a-z0-9_-]*$'", name="ck_mcp_servers_mcp_server_name_slug"),
        sa.CheckConstraint("transport IN ('stdio', 'streamable_http', 'sse')", name="ck_mcp_servers_transport"),
        sa.CheckConstraint(
            "transport <> 'stdio' OR (command IS NOT NULL AND server_url IS NULL AND headers IS NULL)",
            name="ck_mcp_servers_stdio_fields",
        ),
        sa.CheckConstraint(
            "transport = 'stdio' OR (server_url IS NOT NULL AND command IS NULL AND args IS NULL AND env IS NULL)",
            name="ck_mcp_servers_remote_fields",
        ),
        comment="MCP servers, local (stdio process) or remote (http)",
    )
    op.execute(
        "CREATE TRIGGER trg_mcp_servers_set_updated_at BEFORE UPDATE ON mcp_servers "
        "FOR EACH ROW WHEN (OLD.* IS DISTINCT FROM NEW.*) EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    op.drop_table("mcp_servers")
