"""create sync_jobs

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-30 21:10:11.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sync_jobs",
        sa.Column("sync_job_id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("connector_id", sa.Uuid(), nullable=False),
        sa.Column("celery_task_id", sa.Text(), nullable=True, comment="To check on / cancel the celery task"),
        sa.Column(
            "trigger",
            sa.Text(),
            nullable=False,
            comment="scheduled (celery beat, from connectors.refresh_interval_seconds) / manual (admin page)",
        ),
        sa.Column(
            "status",
            sa.Text(),
            server_default="pending",
            nullable=False,
            comment="pending / running / success / failed / cancelled",
        ),
        sa.Column(
            "docs_found",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
            comment="Files listed in the source",
        ),
        sa.Column(
            "docs_indexed",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
            comment="New or changed files that were parsed + embedded",
        ),
        sa.Column(
            "docs_skipped",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
            comment="Unchanged files (same source_version or content_hash)",
        ),
        sa.Column(
            "docs_deleted",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
            comment="Files gone from the source, removed from OpenSearch",
        ),
        sa.Column(
            "docs_failed",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
            comment="Files that failed to parse / embed (reason in documents.error)",
        ),
        sa.Column("error", sa.Text(), nullable=True, comment="Why the job failed, if it did"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When the job was queued",
        ),
        sa.PrimaryKeyConstraint("sync_job_id", name="pk_sync_jobs"),
        sa.ForeignKeyConstraint(
            ["connector_id"],
            ["connectors.connector_id"],
            name="fk_sync_jobs_connector_id_connectors",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("trigger IN ('scheduled', 'manual')", name="ck_sync_jobs_trigger"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'success', 'failed', 'cancelled')", name="ck_sync_jobs_status"
        ),
        sa.CheckConstraint(
            "docs_found >= 0 AND docs_indexed >= 0 AND docs_skipped >= 0 AND docs_deleted >= 0 AND docs_failed >= 0",
            name="ck_sync_jobs_doc_counts_non_negative",
        ),
        sa.CheckConstraint("finished_at >= started_at", name="ck_sync_jobs_finished_after_started"),
        comment="One row per connector sync job run by a celery worker",
    )
    # a connector's job history, newest first (also covers the FK cascade)
    op.create_index("ix_sync_jobs_connector_id_created_at", "sync_jobs", ["connector_id", "created_at"])
    # at most one pending / running job per connector, so celery beat and a manual trigger can't sync it twice
    op.create_index(
        "uq_sync_jobs_connector_id_active",
        "sync_jobs",
        ["connector_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )


def downgrade() -> None:
    op.drop_table("sync_jobs")
