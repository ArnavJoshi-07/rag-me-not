"""Alembic environment.

The database URL is built from the same POSTGRES_* env vars the postgres container reads,
so there is no second copy of the credentials in alembic.ini.
"""

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import URL, create_engine, pool, text

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# set to the models' Base.metadata once they exist, so `alembic revision --autogenerate` can diff against it
target_metadata = None

# pg_advisory_lock key: only one `alembic upgrade` runs at a time, e.g. when several containers start together.
# any constant works, it only has to stay the same
MIGRATION_LOCK_KEY = 7_216_184_201


def _password() -> str:
    # POSTGRES_PASSWORD_FILE lets the password come from a Docker / Kubernetes secret instead of an env var
    if path := os.environ.get("POSTGRES_PASSWORD_FILE"):
        return Path(path).read_text().strip()
    return os.environ["POSTGRES_PASSWORD"]


def database_url() -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=os.environ["POSTGRES_USER"],
        password=_password(),
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ["POSTGRES_DB"],
    )


def run_migrations_offline() -> None:
    """Print the SQL instead of running it (`alembic upgrade head --sql`), no database needed."""
    context.configure(
        dialect_name="postgresql",
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(
        database_url(),
        poolclass=pool.NullPool,
        connect_args={"application_name": "alembic"},
    )

    with engine.connect() as connection:
        # session-level lock, released when the connection closes. a second migrator waits here,
        # then finds the schema already at head and does nothing
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
        connection.commit()

        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
