"""On-disk index: embedding matrix + BM25 + chunk metadata (data/index/).

Storage is deliberately simple (numpy + bm25s + JSONL) because the corpus is a few thousand chunks;
swap `Index` for pgvector/Qdrant later without touching the retrieval logic.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import bm25s
import numpy as np

from ..core import config as C
from ..core.llm import embed
from ..core.utils import read_jsonl, sha256, write_jsonl

# Bilingual stopwords, no stemming: keeps codes like "MARPOL", "PM 29" or "Pt.1" intact for exact matching.
STOPWORDS = set("""a an the of and or to in on for with by from at as is are was were be been this that these those it its
which who what when where how why do does did can will would should may not no into about over than then there their our
your you we they he she his her i me my also such per via
yang dan di ke dari untuk dengan pada dalam adalah ini itu atau oleh sebagai akan tidak juga serta para bagi telah sudah
dapat bisa ada saat karena agar kami kita mereka anda nya pun hal secara antara lebih tersebut apa siapa kapan dimana
bagaimana mengapa berapa""".split())


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+(?:[.\-/][a-z0-9]+)*", text.lower()) if t not in STOPWORDS]


class Index:
    def __init__(self, path: Path = C.INDEX_DIR):
        self.path = path
        self.chunks: list[dict] = list(read_jsonl(path / "chunks.jsonl"))
        self.emb = np.load(path / "embeddings.npy")
        self.bm25 = bm25s.BM25.load(str(path / "bm25"))
        self.meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))

    def vector_search(self, qvec: np.ndarray, k: int) -> list[tuple[int, float]]:
        scores = self.emb @ qvec
        top = np.argsort(-scores)[:k]
        return [(int(i), float(scores[i])) for i in top]

    def bm25_search(self, query: str, k: int) -> list[tuple[int, float]]:
        toks = tokenize(query)
        if not toks:
            return []
        docs, scores = self.bm25.retrieve([toks], k=min(k, len(self.chunks)), show_progress=False)
        return [(int(d), float(s)) for d, s in zip(docs[0], scores[0]) if s > 0]


def embed_cached(texts: list[str], model: str = C.EMBED_MODEL) -> np.ndarray:
    """Embeddings cached by text hash, so re-indexing only pays for new or changed chunks."""
    cache_dir = C.CACHE_DIR / f"emb_{model}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    keys = [sha256(t) for t in texts]
    store_f = cache_dir / "store.npz"
    store = dict(np.load(store_f)) if store_f.exists() else {}
    missing = [i for i, k in enumerate(keys) if k not in store]
    if missing:
        print(f"[index] embedding {len(missing)} texts with {model} ({len(texts) - len(missing)} cached)")
        vecs = embed([texts[i] for i in missing], model=model)
        for i, v in zip(missing, vecs):
            store[keys[i]] = v
        np.savez(store_f, **store)
    return np.stack([store[k] for k in keys])


def build(chunks: list[dict], out: Path, use_context: bool, embed_model: str = C.EMBED_MODEL) -> None:
    """Write an index directory. `search_text` = context + chunk is what gets embedded and BM25-indexed."""
    for c in chunks:
        c["search_text"] = (c.get("context", "") + "\n\n" + c["text"]).strip() if use_context else c["text"]
    emb = embed_cached([c["search_text"] for c in chunks], model=embed_model)
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "embeddings.npy", emb)
    retriever = bm25s.BM25()
    retriever.index([tokenize(c["search_text"]) for c in chunks], show_progress=False)
    retriever.save(str(out / "bm25"))
    write_jsonl(out / "chunks.jsonl", chunks)
    (out / "meta.json").write_text(json.dumps({"embed_model": embed_model, "contextual": use_context,
                                               "chunks": len(chunks)}, indent=1), encoding="utf-8")
    print(f"[index] wrote {out.relative_to(C.ROOT)}: {len(chunks)} chunks, contextual={use_context}, {embed_model}")
