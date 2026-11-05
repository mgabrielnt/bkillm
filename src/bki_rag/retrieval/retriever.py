"""Hybrid retriever: question variants (EN + ID) -> vector + BM25 search -> Reciprocal Rank Fusion."""
from __future__ import annotations

import time

from ..core import config as C
from ..core.llm import embed
from ..indexing.store import Index
from .query import detect_lang, plain_query, rewrite_query


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
        detect_lang("Muat data bahasa sekarang, bukan saat pertanyaan pertama.")

    # Mengembalikan {"query": hasil rewrite, "chunks": top_k chunk untuk jawaban, "ranking": urutan lengkap
    # untuk metrik evaluasi}.
    def search(self, question: str, history: list[dict] | None = None, top_k: int = C.TOP_K) -> dict:
        ix = self.index
        t0 = time.time()
        q = rewrite_query(question, history) if history or C.REWRITE_FIRST_QUESTION else plain_query(question)
        t1 = time.time()
        variants = list(dict.fromkeys(v for v in (q.get("standalone"), q.get("en"), q.get("id")) if v))
        vectors = embed(variants, model=ix.meta["embed_model"], timeout=C.QUERY_EMBED_TIMEOUT_S)
        t2 = time.time()
        ranked = [ix.vector_search(v, C.CANDIDATES_PER_QUERY) for v in vectors]
        keywords = q.get("keywords", "")
        ranked += [ix.bm25_search(f"{v} {keywords}", C.CANDIDATES_PER_QUERY) for v in variants]
        candidates = [ix.chunks[i] for i in reciprocal_rank_fusion(ranked)]
        timing = {"rewrite_s": round(t1 - t0, 3), "embed_s": round(t2 - t1, 3),
                  "search_s": round(time.time() - t2, 3)}
        return {"query": q, "chunks": candidates[:top_k], "ranking": candidates, "timing": timing}
