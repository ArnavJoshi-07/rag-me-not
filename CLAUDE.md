# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

rag-me-not is a self-hostable AI agent builder: documents, LLMs, MCP tools and a code sandbox are combined into agents you chat with, and answers that use documents are cited. It is in early development. The only code so far is the Postgres schema (Alembic migrations in `backend/alembic/versions/`) with its Docker setup, and the embeddings service (`embeddings/`: Hugging Face TEI serving `nomic-embed-text-v1` on ONNX Runtime, CPU only, as two compose services; why: `docs/adr/0001-embeddings-tei-onnx.md`). Everything else in `README.md` (agent loop, tool contract, ingestion pipeline, frontend) is the **target design**, not existing code. Read the README before building any of it. Its "Rules the loop follows" and "Standard tool-call format" sections are the spec.

`CONTEXT.md` is the glossary (Document, Chunk, Query, Chunk prefix, Query prefix). Use its terms in code, comments and docs. Decisions and their reasons are in `docs/adr/`.

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

Tests marked `db` need the compose Postgres running (`docker compose up -d postgres` from the repo root), and without `--env-file ../.env` they can't find it. Tests marked `embeddings` need both embeddings services running (below). Either way, missing services make them **skipped, not failed**, so check the skip summary. The migration round-trip test creates its own throwaway database and never touches the dev database.

Migrations:

```bash
docker compose up                                                  # repo root: starts postgres and the embeddings services, the `migrate` service runs `alembic upgrade head` and exits
uv run --env-file ../.env alembic -c alembic/alembic.ini current   # from backend/, against the local postgres
uv run alembic -c alembic/alembic.ini revision -m "create foo" --rev-id 0018   # next number in sequence
```

Embeddings services, from the repo root:

```bash
docker compose up -d embeddings-indexing embeddings-query   # healthy in ~5 s, ports 8091 / 8090 on 127.0.0.1
docker compose build embeddings-indexing                    # after editing embeddings/Dockerfile. `up` only builds a missing image
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
- **Embeddings:** ingestion calls `http://embeddings-indexing`, chat calls `http://embeddings-query`, both at `POST /v1/embeddings` (OpenAI format). Both always return normalized 768-dim vectors. Ingestion and chat never share a TEI instance: TEI runs one batch at a time from a FIFO queue, so on a shared instance Query p95 was 2.6 s, against 39 ms on a separate query instance. The caller adds the Query prefix or Chunk prefix from the model's `embedding_models` row (`query_prefix`, `chunk_prefix`). The service never adds one.
- **Chunk cap:** 2048 tokens, counted with the model's tokenizer and including the Chunk prefix and the 2 special tokens. Over the cap, indexing returns a 422 with `` `inputs` must have less than 2048 tokens. Given: N `` (2048 itself is accepted). Ingestion then splits the Chunk into neighbour Chunks and retries. Chunks are never truncated. Match that message, not just the status: more than 32 inputs in one request, or an input over 512000 characters, also gets a 422. One over-cap Chunk fails the whole request, the error doesn't say which Chunk it was, and TEI still embeds the request's other Chunks before it fails, so that work is wasted. That is why ingestion sends at most 8 Chunks per request, one batch (ONNX Runtime forces `MAX_BATCH_REQUESTS=8`). TEI itself accepts up to 32 per request (`MAX_CLIENT_BATCH_SIZE`) and runs them 8 at a time. A request of 8 Chunks of ~2000 tokens took up to 34 s under load, so give the client a timeout well above that. `embeddings-query` truncates to 2048 instead.
- **Embeddings memory:** `MAX_BATCH_TOKENS` (4096 on indexing, 2048 on query) bounds memory. TEI pads a batch to its longest input, and the default of 16384 peaked at 8.8 GiB. The `mem_limit` defaults are sized from measurements at those values, so re-measure both if either changes.
- **Secrets:** columns marked encrypted in `database_schema.txt` share one Fernet key from an env var and are never returned by the API.
