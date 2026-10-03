# Serve embeddings with TEI on ONNX Runtime, not an Onyx-style PyTorch server

`nomic-embed-text-v1` runs on CPU only, using Hugging Face Text Embeddings Inference (TEI) 1.9.4 with its ONNX Runtime engine. It does not run in our own FastAPI + sentence-transformers server like the one Onyx uses as its model server.

TEI gives us batching, health checks and metrics without any server code of ours. It ships a CPU-only image with no CUDA. We benchmarked on a Zen 4 laptop at 4 CPUs, embedding 512-token Chunks sent 8 per request:

| Setup | Chunks/s |
|---|---|
| TEI on ONNX Runtime | 3.1 |
| Onyx's encode path (sentence-transformers on CPU-only PyTorch) | 2.1 |
| TEI's default candle engine | 1.0 |

TEI on ONNX Runtime matched sentence-transformers' vectors exactly (cosine distance about 1e-12) at every length up to the 2048-token cap. Onyx's server is built to load any model and to use a GPU when one is present. Its PyTorch install includes CUDA, so we would have had to rebuild it for CPU and then maintain it ourselves.

We still follow Onyx's deployment pattern:
- separate indexing and query instances from one image
- CPU thread counts capped to the container's limit
- Chunks sized with the model's own tokenizer
- Query and Chunk prefixes stored on the embedding model's row

## Consequences

- **Ingestion and chat must never share a TEI instance.** TEI runs one batch at a time from a FIFO queue, so a Query waits for the whole batch already running. On one shared instance during ingestion, Query p95 was 2.6 s. Onyx's server encodes concurrently and got 51 ms in the same test. With a separate query instance at 2 CPUs, TEI's Query p95 was 39 ms, and ingestion speed didn't change. The cost is the extra CPUs and memory of a second process.
- **The image deletes two fields from the model's `config.json`.** The fields are `hidden_size` and `num_hidden_layers`. The model's "v5 Transformers" revision, the one we pin, added them next to `n_embd` and `n_layer`, which TEI reads as other names for the same fields. With both spellings present, TEI's ONNX engine refuses to load the model (`duplicate field hidden_size`). Don't "fix" it back. Re-check it whenever TEI or the model revision is upgraded, because the clash depends on how that TEI version names these fields. The `embeddings` parity test fails if vectors drift.
- **TEI and the model revision are both pinned.** TEI is pinned by digest and the model by commit SHA. Any change to either can change the vectors, so test it with the parity test before deploying. Vectors that already exist in OpenSearch were produced by the old pair.
