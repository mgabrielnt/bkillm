"""Stage 5 orchestration: chunks.jsonl -> (contextual retrieval) -> embeddings + BM25 in data/index/."""
from __future__ import annotations

from ..core import config as C
from ..core.utils import read_jsonl
from .contextualize import add_context
from .store import build


def run(contextualize: bool = True) -> None:
    chunks = list(read_jsonl(C.CHUNKS_FILE))
    if contextualize:
        add_context(chunks)
    build(chunks, C.INDEX_DIR, use_context=contextualize)
