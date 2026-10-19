"""Hybrid retriever: query variants -> vector + BM25 search -> Reciprocal Rank Fusion -> (optional rerank)."""
from __future__ import annotations

from dataclasses import dataclass

from ..core import config as C
from ..core.llm import embed
from ..indexing.store import Index
from .query import detect_lang, rewrite_query
from .rerank import rerank


# Pengaturan pencarian: pakai BM25, rewrite pertanyaan, rerank, dan jumlah chunk (top_k).
@dataclass(frozen=True)
class RetrievalConfig:
    name: str = "full"
    bm25: bool = True
    rewrite: bool = True
    rerank: bool = False  # lihat rerank.py: mengapa ini tidak aktif secara default
    top_k: int = C.TOP_K


# Gabungkan beberapa daftar peringkat: item yang tinggi di banyak daftar naik ke atas.
def reciprocal_rank_fusion(ranked_lists: list[list[tuple[int, float]]], k: int = C.RRF_K) -> list[int]:
    fused: dict[int, float] = {}
    for lst in ranked_lists:
        for rank, (idx, _) in enumerate(lst):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return sorted(fused, key=lambda i: -fused[i])


# Pencari hybrid: vektor + BM25 untuk setiap versi pertanyaan, digabung dengan RRF.
class Retriever:
    # Cari di index yang diberikan (default: data/index).
    def __init__(self, index: Index | None = None):
        self.index = index or Index()

    # Mengembalikan {"query": hasil rewrite, "chunks": top_k chunk untuk jawaban, "ranking": urutan lengkap
    # untuk metrik}.
    def search(self, question: str, history: list[dict] | None = None,
               cfg: RetrievalConfig = RetrievalConfig()) -> dict:
        ix = self.index
        q = rewrite_query(question, history) if cfg.rewrite else {"standalone": question, "lang": detect_lang(question)}
        variants = list(dict.fromkeys(v for v in (q.get("standalone"), q.get("en"), q.get("id")) if v))
        ranked_lists = [ix.vector_search(v, C.CANDIDATES_PER_QUERY) for v in embed(variants, model=ix.meta["embed_model"])]
        if cfg.bm25:
            kw = q.get("keywords", "")
            ranked_lists += [ix.bm25_search(f"{v} {kw}", C.CANDIDATES_PER_QUERY) for v in variants]
        candidates = [ix.chunks[i] for i in reciprocal_rank_fusion(ranked_lists)]
        if not cfg.rerank:
            return {"query": q, "chunks": candidates[:cfg.top_k], "ranking": candidates}
        ranked = rerank(q["standalone"], candidates[:C.RERANK_POOL])
        chunks = [c for c, s in ranked if s >= 1][:cfg.top_k] or [c for c, _ in ranked[:3]]
        return {"query": q, "chunks": chunks, "ranking": [c for c, _ in ranked] + candidates[C.RERANK_POOL:]}
