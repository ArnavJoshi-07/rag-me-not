"""Writes nomic_reference_vectors.json, the vectors test_embeddings.py compares both embeddings services against.

The reference is sentence-transformers on CPU-only PyTorch, the model's own reference implementation, at the same
model revision the embeddings image bakes in. Run from backend/:

    uv run --no-project --with sentence-transformers --index https://download.pytorch.org/whl/cpu \\
        python tests/fixtures/make_nomic_reference_vectors.py

--no-project keeps sentence-transformers and torch out of the project's environment and uv.lock.
The first run downloads the model's safetensors weights (550 MB) into the Hugging Face cache.

Re-run it only when the model revision changes, together with MODEL_REVISION in embeddings/Dockerfile.
"""

import json
from importlib.metadata import version
from pathlib import Path

from sentence_transformers import SentenceTransformer  # pyright: ignore[reportMissingImports]

MODEL = "nomic-ai/nomic-embed-text-v1"
# must match MODEL_REVISION in embeddings/Dockerfile
REVISION = "3ac47f125a41961d13b397d0332866be2f9152e1"
QUERY_PREFIX = "search_query: "
CHUNK_PREFIX = "search_document: "
OUT = Path(__file__).with_name("nomic_reference_vectors.json")

# a Chunk right at the 2048-token cap, the longest one ingestion sends
LONG_CHUNK_TOKENS = 2048

HANDBOOK = [
    "Every connector syncs on its own schedule. When a sync starts, the worker lists the files in the source and "
    "compares each one with the row it already has. A file whose ETag or modified time has not changed is skipped "
    "without being downloaded.",
    "Changed files are downloaded to staging, parsed, and split into Chunks of at most 2048 tokens. Each Chunk keeps "
    "a link to its neighbours and to its parent, so an answer can quote the text around a match.",
    "The on-call engineer checks the sync dashboard twice a day. A connector that has failed three times in a row "
    "is paused, and its owner gets an email with the last error message and a link to the job log.",
    "Credentials are encrypted with a single Fernet key read from the environment. Rotating the key means "
    "decrypting every secret with the old key and encrypting it again with the new one, inside one transaction.",
    "Deleting a connector removes its documents from Postgres straight away. Their Chunks are removed from the "
    "search index by a background job, which retries until the index confirms that nothing is left.",
    "Quarterly reviews look at three numbers: how many documents failed to parse, how long a full sync takes, and "
    "how often a search returned nothing. Each number is compared with the same quarter of the previous year.",
]


def long_chunk(model: SentenceTransformer) -> str:
    """Handbook sections, numbered and repeated, cut to exactly LONG_CHUNK_TOKENS tokens (special tokens included)."""
    sections: list[str] = []
    i = 0
    while len(model.tokenizer(CHUNK_PREFIX + "\n\n".join(sections))["input_ids"]) < LONG_CHUNK_TOKENS:
        sections.append(f"Section {i + 1}. {HANDBOOK[i % len(HANDBOOK)]}")
        i += 1
    # the last section overshoots the cap: cut the text where the last token that fits ends.
    # token 0 is [CLS], so token LONG_CHUNK_TOKENS - 2 is the last one before [SEP]
    text = CHUNK_PREFIX + "\n\n".join(sections)
    end = model.tokenizer(text, return_offsets_mapping=True)["offset_mapping"][LONG_CHUNK_TOKENS - 2][1]
    chunk = text[len(CHUNK_PREFIX) : end]
    tokens = len(model.tokenizer(CHUNK_PREFIX + chunk)["input_ids"])
    assert tokens == LONG_CHUNK_TOKENS, f"the cut split a word and it re-tokenized to {tokens} tokens, move the cut"
    return chunk


def main() -> None:
    model = SentenceTransformer(MODEL, revision=REVISION, trust_remote_code=False, device="cpu")

    texts = [
        QUERY_PREFIX + "How do I rotate the key that encrypts connector credentials?",
        # accents, CJK and an emoji, so the tokenizers' normalization has to agree too
        QUERY_PREFIX + "Wie viele Urlaubstage habe ich im ersten Jahr? Ça dépend du contrat, 休暇の申請 🏖️",
        CHUNK_PREFIX + HANDBOOK[0] + " " + HANDBOOK[1],
        CHUNK_PREFIX
        + "| Status | Meaning |\n|---|---|\n| pending | queued, not started |\n| failed | see documents.error |\n\n"
        + "```python\ndef retry(job):\n    return job.attempts < 3 and job.status == 'failed'\n```",
        CHUNK_PREFIX + long_chunk(model),
    ]
    vectors = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)

    entries = [
        {
            "text": text,
            "tokens": len(model.tokenizer(text)["input_ids"]),
            "vector": [round(float(x), 8) for x in vector],
        }
        for text, vector in zip(texts, vectors, strict=True)
    ]
    fixture = {
        "model": MODEL,
        "revision": REVISION,
        "generated_with": {pkg: version(pkg) for pkg in ("sentence-transformers", "transformers", "torch")},
        "entries": entries,
    }
    OUT.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n")
    for entry in entries:
        print(f"{entry['tokens']:>5} tokens  {entry['text'][:60]!r}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
