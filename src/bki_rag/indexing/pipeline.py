"""Stage 5 orchestration: chunks.jsonl -> chunk contexts -> embeddings + BM25 in data/index/."""
from __future__ import annotations

from ..core import config as C
from ..core.utils import read_jsonl
from .contextualize import add_context
from .store import build


# Bangun data/index dari data/processed/chunks.jsonl: beri konteks tiap chunk, lalu embedding + BM25.
def run() -> None:
    chunks = list(read_jsonl(C.CHUNKS_FILE))
    add_context(chunks)
    build(chunks, C.INDEX_DIR)
