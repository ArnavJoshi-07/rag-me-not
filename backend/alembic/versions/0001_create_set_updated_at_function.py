"""create set_updated_at() trigger function

Shared by every table with an updated_at column. Each of those tables gets a
BEFORE UPDATE trigger that calls it, so updated_at is kept by the database no
matter which code path ran the UPDATE.

Revision ID: 0001
Revises:
Create Date: 2026-09-30 21:10:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION set_updated_at() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at := now();
            RETURN NEW;
        END;
        $$
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION set_updated_at()")
