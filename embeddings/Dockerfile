# syntax=docker/dockerfile:1

# TEI's CPU-only image: amd64 only, no CUDA. releases before 1.9.4 crash on the model's current config.
# a new TEI or model revision can change the vectors, run the embeddings tests before deploying it (docs/adr/0001)
ARG TEI_IMAGE=ghcr.io/huggingface/text-embeddings-inference:cpu-1.9.4@sha256:2538ea1c9640d3763b15af668039d24172d063b42337b0c27796fc2be180c78d

# ---- download: the model files at a pinned revision, every one sha256-checked ----
# the TEI image has curl, so it doubles as the download stage. only /model is copied out of it
FROM ${TEI_IMAGE} AS download

# the sha256s below only match this revision
ARG MODEL_REVISION=3ac47f125a41961d13b397d0332866be2f9152e1
ARG MODEL_URL=https://huggingface.co/nomic-ai/nomic-embed-text-v1/resolve/${MODEL_REVISION}

WORKDIR /model

# the ONNX weights only, no model.safetensors: TEI tries ONNX Runtime first and falls back to its candle engine
# (3.6x slower on CPU). with no safetensors that fallback fails too, so an ONNX load error stops the container.
# own layer, so a change further down doesn't download 550 MB again. the sha256 is the file's lfs.oid from
# https://huggingface.co/api/models/nomic-ai/nomic-embed-text-v1/tree/<revision>?recursive=true
# mkdir, not curl --create-dirs: curl makes its dirs 0750, which the app user can't read
RUN mkdir -p onnx \
 && curl -fsSL --retry 3 -o onnx/model.onnx "$MODEL_URL/onnx/model.onnx" \
 && echo "347440e93b5ec979fdcf6041b72721aade7b9680c16022e2830db7115ff6fd9f  onnx/model.onnx" | sha256sum -c --strict -

# 1_Pooling/config.json is required in practice: without it TEI silently uses CLS pooling, this model uses mean pooling
RUN mkdir -p 1_Pooling \
 && for f in config.json tokenizer.json tokenizer_config.json special_tokens_map.json sentence_bert_config.json \
        1_Pooling/config.json; do \
      curl -fsSL --retry 3 -o "$f" "$MODEL_URL/$f" || exit 1; \
    done \
 && printf '%s\n' \
      "913351bb022df8c2b332dc955145dea342380b162d532af756b3bdba3b3a1cfb  config.json" \
      "d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66  tokenizer.json" \
      "d7e0000bcc80134debd2222220427e6bf5fa20a669f40a0d0d1409cc18e0a9bc  tokenizer_config.json" \
      "b6d346be366a7d1d48332dbc9fdf3bf8960b5d879522b7799ddba59e76237ee3  special_tokens_map.json" \
      "eb9b44b13c0f52a3b3685c3b1cbdea1ba8b04bea123b98f61610048940776eb1  sentence_bert_config.json" \
      "f2fa6333d3899e2f9368e2e2741ece8e74160337b3698f475f6e0f7f28e396fe  1_Pooling/config.json" \
    | sha256sum -c --strict -

# config.json: TEI's ONNX loader reads hidden_size and num_hidden_layers, and also accepts n_embd and n_layer as other
# names for the same fields. the model's "v5 Transformers" revision added the long names next to the n_* ones, so
# loading fails with "duplicate field `hidden_size`". the long names go, the n_* ones hold the same values (768, 12).
# num_attention_heads stays: the loader never reads it (its n_head alias is for num_key_value_heads).
# don't drop this patch, and re-check it whenever TEI or the model revision changes.
# why: docs/adr/0001-embeddings-tei-onnx.md
#
# sentence_bert_config.json: TEI has no flag for the input cap, it reads max_seq_length from this file. above 2048
# tokens the model's current config gives vectors that differ from its trained behaviour, and long inputs get slow
# (8192 tokens took 72 s on 4 CPUs)
#
# the second sha256 check proves sed changed exactly those lines and nothing else
RUN sed -i -e '/^  "hidden_size": 768,$/d' \
           -e '/^  "num_hidden_layers": 12,$/d' config.json \
 && sed -i 's/^  "max_seq_length": 8192,$/  "max_seq_length": 2048,/' sentence_bert_config.json \
 && printf '%s\n' \
      "7e18cbb3cbe5cdc4bf5083ebceed04377e30bd4d25d490a4714ca64932b8a06b  config.json" \
      "d7ff3be36cdd7a6eeb94411121036d669cb1074eb1540dabd3e3cb18ee13e3a6  sentence_bert_config.json" \
    | sha256sum -c --strict -

# ---- runtime: TEI with the model baked in, needs no network, runs as a non-root user ----
FROM ${TEI_IMAGE} AS runtime

RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

# a local path: TEI loads the model from disk and never contacts the Hugging Face Hub
ENV MODEL_ID=/model

# owned by root, read-only for the app user
COPY --from=download /model /model

USER app

# ENTRYPOINT ["text-embeddings-router"] and CMD ["--json-output"] come from the TEI image.
# everything else is set per service through env vars in docker-compose.yml
