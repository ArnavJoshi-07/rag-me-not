"""Embeddings service checks, against the compose services embeddings-indexing and embeddings-query.

Parity: both services must give the vectors sentence-transformers gives for the same prefixed text
(fixtures/nomic_reference_vectors.json, written by fixtures/make_nomic_reference_vectors.py). A drift means a new
TEI image or model revision changed the vectors, so Chunks already in OpenSearch would no longer match new Queries.

Cap: indexing must reject a Chunk over 2048 tokens with the exact error ingestion's split-and-retry relies on,
and query must cut the same text to 2048 tokens instead of failing.
"""

import json
import math
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.embeddings

FIXTURE = Path(__file__).parent / "fixtures" / "nomic_reference_vectors.json"

# compose service -> (env var with its host port, default port), as in docker-compose.yml
SERVICES = {
    "embeddings-indexing": ("EMBEDDINGS_INDEXING_PORT", 8091),
    "embeddings-query": ("EMBEDDINGS_QUERY_PORT", 8090),
}
MAX_TOKENS = 2048
DIMS = 768
CHUNK_PREFIX = "search_document: "
# a 2048-token text takes a few seconds on 2 CPUs, and /health waits behind any batch already running
TIMEOUT = 120


def service_url(name: str) -> str:
    port_var, default_port = SERVICES[name]
    url = f"http://127.0.0.1:{os.environ.get(port_var, default_port)}"
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=TIMEOUT):
            pass
    except urllib.error.HTTPError:
        raise  # it answered, so it's up but unhealthy: a failure, not a skip
    except urllib.error.URLError as e:
        pytest.skip(f"{name} is not reachable at {url}, start it with `docker compose up -d {name}` ({e.reason})")
    return url


@pytest.fixture(scope="module")
def indexing() -> str:
    return service_url("embeddings-indexing")


@pytest.fixture(scope="module")
def query() -> str:
    return service_url("embeddings-query")


@pytest.fixture(scope="module", params=list(SERVICES))
def service(request: pytest.FixtureRequest) -> str:
    return service_url(request.param)


def post(url: str, payload: dict[str, Any]) -> tuple[int, Any]:
    """POST json, return (status, parsed body) for error responses too."""
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as e:
        with e:
            return e.code, json.loads(e.read())


def embed(url: str, texts: list[str]) -> list[list[float]]:
    status, body = post(f"{url}/v1/embeddings", {"input": texts})
    assert status == 200, body
    return [item["embedding"] for item in body["data"]]


def cosine(a: list[float], b: list[float]) -> float:
    return math.sumprod(a, b) / math.sqrt(math.sumprod(a, a) * math.sumprod(b, b))


def chunk_of(url: str, tokens: int) -> str:
    """A prefixed Chunk of exactly `tokens` tokens, special tokens included, as the chunker will count them."""
    # [CLS] + "search_document: " (4 tokens) + one token per "a" + [SEP]
    text = CHUNK_PREFIX + " ".join(["a"] * (tokens - 6))
    status, body = post(f"{url}/tokenize", {"inputs": text})
    assert status == 200, body
    assert len(body[0]) == tokens, "the count above is off, fix chunk_of"
    return text


def test_matches_reference_vectors(service: str) -> None:
    reference = json.loads(FIXTURE.read_text())["entries"]

    vectors = embed(service, [entry["text"] for entry in reference])

    for entry, vector in zip(reference, vectors, strict=True):
        similarity = cosine(vector, entry["vector"])
        assert similarity >= 0.9999, f"{entry['tokens']}-token text drifted to cosine {similarity:.6f}"


def test_vectors_are_768_dims_and_normalized(service: str) -> None:
    [vector] = embed(service, ["search_query: how do I add a connector?"])

    assert len(vector) == DIMS
    assert math.sqrt(math.sumprod(vector, vector)) == pytest.approx(1.0, abs=1e-5)


def test_indexing_accepts_chunk_at_cap(indexing: str) -> None:
    [vector] = embed(indexing, [chunk_of(indexing, MAX_TOKENS)])

    assert len(vector) == DIMS


def test_indexing_rejects_chunk_over_cap(indexing: str) -> None:
    # ingestion parses this to split the Chunk and retry. "less than 2048" is TEI's wording, 2048 itself is accepted
    status, body = post(f"{indexing}/v1/embeddings", {"input": [chunk_of(indexing, MAX_TOKENS + 1)]})

    assert status == 422
    assert body == {
        "message": f"Input validation error: `inputs` must have less than {MAX_TOKENS} tokens. Given: {MAX_TOKENS + 1}",
        "code": 422,
        "type": "Validation",
    }


def test_query_truncates_over_cap(query: str) -> None:
    status, body = post(f"{query}/v1/embeddings", {"input": [chunk_of(query, MAX_TOKENS + 1)]})

    assert status == 200, body
    assert len(body["data"][0]["embedding"]) == DIMS
    assert body["usage"]["prompt_tokens"] == MAX_TOKENS
