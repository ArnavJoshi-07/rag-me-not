"""create llm_models

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-30 21:10:03.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_models",
        sa.Column("model_id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False, comment="LiteLLM model string, e.g. ollama/llama3.1"),
        sa.Column("display_name", sa.Text(), nullable=False, comment="Shown in the model picker"),
        sa.Column("context_window", sa.Integer(), nullable=True, comment="Max input tokens"),
        sa.Column("max_output_tokens", sa.Integer(), nullable=True),
        sa.Column(
            "supports_tools",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
            comment="Only models that can call tools are offered in the chat model picker",
        ),
        sa.Column(
            "supports_vision",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
            comment="Needed for image / chart summaries during ingestion and image uploads in chat",
        ),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("model_id", name="pk_llm_models"),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["llm_providers.provider_id"],
            name="fk_llm_models_provider_id_llm_providers",
            ondelete="CASCADE",
        ),
        # also serves as the index for provider_id lookups and the FK cascade
        sa.UniqueConstraint("provider_id", "model_name", name="uq_llm_models_provider_id_model_name"),
        sa.CheckConstraint("context_window > 0", name="ck_llm_models_context_window_positive"),
        sa.CheckConstraint("max_output_tokens > 0", name="ck_llm_models_max_output_tokens_positive"),
        comment=(
            "Models offered by each provider. context_window, max_output_tokens and supports_* can be prefilled "
            "from litellm.get_model_info(model_name) and edited by the admin"
        ),
    )
    op.execute(
        "CREATE TRIGGER trg_llm_models_set_updated_at BEFORE UPDATE ON llm_models "
        "FOR EACH ROW WHEN (OLD.* IS DISTINCT FROM NEW.*) EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    op.drop_table("llm_models")
