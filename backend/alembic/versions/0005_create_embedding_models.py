"""create embedding_models

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-30 21:10:04.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "embedding_models",
        sa.Column("embedding_model_id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("model", sa.Text(), nullable=False, comment="e.g. nomic-embed-text-v1"),
        sa.Column(
            "dims", sa.Integer(), nullable=False, comment="Vector dimensions, must match the OpenSearch k-NN index"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("embedding_model_id", name="pk_embedding_models"),
        sa.UniqueConstraint("model", "dims", name="uq_embedding_models_model_dims"),
        sa.CheckConstraint("dims > 0", name="ck_embedding_models_dims_positive"),
    )
    op.execute(
        "CREATE TRIGGER trg_embedding_models_set_updated_at BEFORE UPDATE ON embedding_models "
        "FOR EACH ROW WHEN (OLD.* IS DISTINCT FROM NEW.*) EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    op.drop_table("embedding_models")
