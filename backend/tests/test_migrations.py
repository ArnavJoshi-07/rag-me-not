"""Migration checks.

The round trip runs on a throwaway database on the compose Postgres, so the dev database is never touched.
It catches a downgrade() that misses something its upgrade() created, which would otherwise only show up
the day someone needs to roll back.
"""

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import URL, Engine, create_engine, text
from sqlalchemy.exc import OperationalError

ALEMBIC_INI = Path(__file__).parents[1] / "alembic" / "alembic.ini"

# what alembic itself leaves in a database at base
ALEMBIC_OWN = {("table", "alembic_version"), ("index", "alembic_version_pkc")}

# everything in the public schema a migration can create. triggers and constraints go with their tables
SCHEMA_OBJECTS = text("""
    SELECT CASE c.relkind WHEN 'r' THEN 'table' WHEN 'i' THEN 'index' WHEN 'S' THEN 'sequence'
                          WHEN 'v' THEN 'view' WHEN 'm' THEN 'matview' ELSE c.relkind::text END,
           c.relname
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
    UNION ALL
    SELECT 'function', p.proname
    FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
    UNION ALL
    SELECT 'type', t.typname  -- enums, domains, ranges. not the row and array types every table gets
    FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'public' AND t.typtype IN ('e', 'd', 'r', 'm')
    UNION ALL
    SELECT 'extension', extname FROM pg_extension WHERE extname <> 'plpgsql'
""")


def schema_objects(engine: Engine) -> set[tuple[str, str]]:
    with engine.connect() as conn:
        return {(kind, name) for kind, name in conn.execute(SCHEMA_OBJECTS)}


@pytest.fixture
def scratch_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    """A new, empty database on the compose Postgres that alembic is pointed at. Dropped afterwards."""
    try:
        url = URL.create(
            "postgresql+psycopg",
            username=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=int(os.environ.get("POSTGRES_PORT", "5432")),
            database=os.environ["POSTGRES_DB"],
        )
    except KeyError as e:
        pytest.skip(f"{e.args[0]} is not set: run with `uv run --env-file ../.env pytest`")

    name = f"{url.database}_test_{uuid.uuid4().hex[:8]}"
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    except OperationalError as e:
        admin.dispose()
        pytest.skip(f"Postgres is not reachable, start it with `docker compose up -d postgres` ({e.orig})")

    # env.py builds its URL from these on every alembic command
    monkeypatch.setenv("POSTGRES_DB", name)
    engine = create_engine(url.set(database=name))
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


def test_single_head() -> None:
    # two heads = two branches each added a migration on the same parent. `upgrade head` refuses to run
    heads = ScriptDirectory.from_config(Config(ALEMBIC_INI)).get_heads()
    assert len(heads) == 1, f"multiple heads {heads}: merge them with `alembic merge heads`"


@pytest.mark.db
def test_upgrade_downgrade_round_trip(scratch_db: Engine) -> None:
    config = Config(ALEMBIC_INI)

    command.upgrade(config, "head")
    at_head = schema_objects(scratch_db)
    assert at_head > ALEMBIC_OWN

    command.downgrade(config, "base")
    assert schema_objects(scratch_db) == ALEMBIC_OWN, "downgrade to base left objects behind"

    command.upgrade(config, "head")
    assert schema_objects(scratch_db) == at_head, "upgrade after a full downgrade built a different schema"
