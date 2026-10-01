# rag-me-not

A self-hostable AI agent builder. Documents, LLMs, MCP tools and a code sandbox are combined into agents you chat with, and any answer that uses documents is cited.

## Language

### Knowledge

**Document**:
One file pulled by a connector. A Document is never embedded as a whole. Its text is split into Chunks.
_Avoid_: Passage

**Chunk**:
A piece of a Document's text that is embedded, searched and cited on its own. It links to its neighbour and parent Chunks.
_Avoid_: Passage, segment, document (for the piece)

**Query**:
The text a knowledge search runs with. The agent writes it when it calls the RAG tool, so it is not the user's message.
_Avoid_: Question, prompt (for the search text)

### Embeddings

**Embedding model**:
The model that turns Chunks and Queries into vectors for knowledge search. It fixes the vector size and its own Query prefix and Chunk prefix.

**Query prefix**:
Text the Embedding model needs in front of a Query before embedding it (`search_query: ` for nomic-embed-text-v1).

**Chunk prefix**:
Text the Embedding model needs in front of a Chunk before embedding it (`search_document: ` for nomic-embed-text-v1, which names it after its own idea of a document, not ours).
_Avoid_: Document prefix, passage prefix
