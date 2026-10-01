# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

rag-me-not is a self-hostable AI agent builder: documents, LLMs, MCP tools and a code sandbox are combined into agents you chat with, and answers that use documents are cited. It is in early development. The only code so far is the Postgres schema (Alembic migrations in `backend/alembic/versions/`) and its Docker setup. Everything else in `README.md` (agent loop, tool contract, ingestion pipeline, frontend) is the **target design**, not existing code. Read the README before building any of it. Its "Rules the loop follows" and "Standard tool-call format" sections are the spec.

`database_schema.txt` is the human-written spec for every table: column meanings, on-delete behaviour, and what gets cleaned up outside Postgres (OpenSearch chunks, MinIO objects). A schema change goes in both the migration and this file.

## Commands

Python lives in `backend/` and is managed with uv (Python 3.14). Run these from `backend/`:

```bash
uv sync                                   # install deps, including the dev group
uv run ruff check . && uv run ruff format --check .
uv run pyright                            # config is ../pyrightconfig.json (found by walking up)
uv run --env-file ../.env pytest          # all tests
uv run --env-file ../.env pytest tests/test_migrations.py::test_upgrade_downgrade_round_trip
```

Tests marked `db` need the compose Postgres running (`docker compose up -d postgres` from the repo root). Without it, or without `--env-file ../.env`, they are **skipped, not failed**, so check the skip summary. The migration round-trip test creates its own throwaway database and never touches the dev database.

Migrations:

```bash
docker compose up                                                  # repo root: starts postgres, the `migrate` service runs `alembic upgrade head` and exits
uv run --env-file ../.env alembic -c alembic/alembic.ini current   # from backend/, against the local postgres
uv run alembic -c alembic/alembic.ini revision -m "create foo" --rev-id 0017   # next number in sequence
```

A PostToolUse hook (`.claude/hooks/ruff.sh`) runs `ruff format` and `ruff check --fix` on every Python file edited under `backend/`. Anything ruff can't fix comes back as hook feedback. Unused imports are reported but deliberately not removed, so an import can be added one edit before the code that uses it.

## Migration conventions

Migrations are hand-written: `target_metadata` is `None` in `env.py` until SQLAlchemy models exist, so `--autogenerate` doesn't work yet. Follow the existing files:

- Revision IDs are zero-padded sequence numbers (`0001`, `0002`, …). Pass `--rev-id` explicitly.
- Primary keys are `sa.Uuid()` with `server_default=sa.text("uuidv7()")`. `uuidv7()` is built into Postgres 18 (the compose image is 18). Join tables use their FK pair as the key.
- Every constraint and index is named explicitly: `pk_<table>`, `fk_<table>_<col>_<referred_table>`, `uq_<table>_<cols>`, `ck_<table>_<what>`, `ix_<table>_<cols>`.
- Enumerated values are `Text` plus a `CHECK ... IN (...)` constraint, not Postgres enum types.
- Tables with `updated_at` get a `BEFORE UPDATE` trigger `trg_<table>_set_updated_at` that calls the shared `set_updated_at()` function from `0001`. The database maintains `updated_at`, not app code.
- Tables carry a `comment=` explaining their role.
- `downgrade()` must drop everything `upgrade()` created, including functions. `test_upgrade_downgrade_round_trip` checks this.

`env.py` builds the database URL from the same `POSTGRES_*` variables the postgres container reads (`POSTGRES_PASSWORD_FILE` is also supported). It takes a `pg_advisory_lock`, so concurrent `upgrade` runs from several containers are safe. Later services (API, workers) should `depends_on: migrate: condition: service_completed_successfully`.

## Design invariants to keep when building the backend

These come from the README and schema spec, and are easy to miss:

- **Tool contract:** every tool (RAG, MCP, sandbox) implements the same `Tool` protocol and returns `ToolResult`s. Every `ToolCall.id` must get exactly one result, even on timeout, exception, or "budget exceeded", because LLM providers reject the next request otherwise.
- **Budget:** at most 5 rounds × 3 calls per round. In round 1 only `rag.*` tools are offered when the analysis says knowledge is needed. This is enforced in code, not in the prompt.
- **Parallelism:** `parallel_safe` tools run concurrently. `sandbox.*` (one shared container) and side-effecting MCP tools run one at a time.
- **Citations** are numbered by the executor and unique across rounds, never by individual tools.
- **History:** later turns see only user messages and final answers. `agent_events` (tool calls, thinking) are for the UI timeline only.
- **RAG scope:** searches only cover the agent's `agent_connectors`. Query analysis may narrow that set but never widen it.
- **Embeddings** (`nomic-embed-text-v1`) need the prefix `search_document: ` when indexing and `search_query: ` when querying.
- **Secrets:** columns marked encrypted in `database_schema.txt` share one Fernet key from an env var and are never returned by the API.
