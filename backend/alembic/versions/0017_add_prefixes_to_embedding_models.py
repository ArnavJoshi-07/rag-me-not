"""add prefixes to embedding_models

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-01 22:23:14.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # callers add the prefix themselves, the embeddings service never does. empty = the model needs none
    op.add_column(
        "embedding_models",
        sa.Column(
            "query_prefix",
            sa.Text(),
            server_default="",
            nullable=False,
            comment="Prepended to a Query before embedding it, trailing space included, e.g. 'search_query: '",
        ),
    )
    op.add_column(
        "embedding_models",
        sa.Column(
            "chunk_prefix",
            sa.Text(),
            server_default="",
            nullable=False,
            comment="Prepended to a Chunk before embedding it, trailing space included, e.g. 'search_document: '",
        ),
    )


def downgrade() -> None:
    op.drop_column("embedding_models", "chunk_prefix")
    op.drop_column("embedding_models", "query_prefix")
