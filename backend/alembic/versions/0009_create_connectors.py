"""create connectors

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-30 21:10:08.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connectors",
        sa.Column("connector_id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("connector_name", sa.Text(), nullable=False),
        sa.Column(
            "connector_source",
            sa.Text(),
            nullable=False,
            comment="s3 / gdrive -> Elastic data-source class, file -> admin uploads to MinIO read by our own code",
        ),
        sa.Column(
            "config",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment="Non-secret settings in the shape the data-source class expects -> bucket name, folder id",
        ),
        sa.Column(
            "credentials",
            sa.Text(),
            nullable=True,
            comment=(
                "Fernet-encrypted JSON of secrets only, merged with config when the data-source class is built. "
                "Never returned by the API"
            ),
        ),
        sa.Column(
            "sync_cursor",
            postgresql.JSONB(),
            nullable=True,
            comment="Returned by the data source after a sync, passed back for an incremental sync. NULL -> full sync",
        ),
        sa.Column("status", sa.Text(), server_default="active", nullable=False, comment="active / paused / error"),
        sa.Column(
            "refresh_interval_seconds",
            sa.Integer(),
            nullable=True,
            comment="How often celery beat syncs the connector. NULL -> manual sync only",
        ),
        sa.Column(
            "last_synced_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the last successful sync finished",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("connector_id", name="pk_connectors"),
        sa.CheckConstraint("connector_source IN ('s3', 'gdrive', 'file')", name="ck_connectors_connector_source"),
        sa.CheckConstraint("status IN ('active', 'paused', 'error')", name="ck_connectors_status"),
        sa.CheckConstraint("jsonb_typeof(config) = 'object'", name="ck_connectors_config_object"),
        sa.CheckConstraint("refresh_interval_seconds > 0", name="ck_connectors_refresh_interval_seconds_positive"),
        comment="Data sources. Holds all connector state, Elasticsearch is not used",
    )
    op.execute(
        "CREATE TRIGGER trg_connectors_set_updated_at BEFORE UPDATE ON connectors "
        "FOR EACH ROW WHEN (OLD.* IS DISTINCT FROM NEW.*) EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    op.drop_table("connectors")
