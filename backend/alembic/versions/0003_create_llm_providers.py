"""create llm_providers

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-30 21:10:02.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_providers",
        sa.Column("provider_id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("provider_name", sa.Text(), nullable=False, comment="Display name"),
        sa.Column(
            "provider_type",
            sa.Text(),
            nullable=False,
            comment="LiteLLM provider type, e.g. anthropic / openai / gemini / ollama",
        ),
        sa.Column(
            "api_key",
            sa.Text(),
            nullable=True,
            comment="Fernet-encrypted, never returned by the API. NULL for ollama / self-hosted models without auth",
        ),
        sa.Column(
            "api_base",
            sa.Text(),
            nullable=True,
            comment="Custom endpoint URL for ollama / self-hosted models. NULL for hosted providers",
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
            comment="Models of a disabled provider are hidden from the model picker",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("provider_id", name="pk_llm_providers"),
        comment="LLM providers reached through LiteLLM",
    )
    op.execute(
        "CREATE TRIGGER trg_llm_providers_set_updated_at BEFORE UPDATE ON llm_providers "
        "FOR EACH ROW WHEN (OLD.* IS DISTINCT FROM NEW.*) EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    op.drop_table("llm_providers")
