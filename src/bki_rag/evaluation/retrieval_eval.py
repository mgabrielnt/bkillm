"""Stage 1: evaluasi temu dokumen (Hit@10, MRR@10)."""
from __future__ import annotations

from typing import Any
from ..core.llm import pmap
from ..retrieval.restricted import match_restricted
from ..retrieval.retriever import Retriever


def _is_hit(chunk: dict, q: dict) -> bool:
    if q.get("group_id") and chunk.get("group_id") == q["group_id"]:
        return True
    return chunk.get("url") in (q.get("urls") or [])


def evaluate_retrieval(retriever: Retriever, golden: list[dict]) -> tuple[dict[str, Any], list[dict]]:
    """Cek apakah dokumen sumber masuk top-10 (Hit@10) dan di urutan ke berapa (MRR@10)."""
    answerable = [q for q in golden if q.get("answerable") and not match_restricted(q["question"])]
    found = pmap(lambda q: retriever.search(q["question"]), answerable, workers=8, desc="retrieve")

    hits, rr_sum = 0, 0.0
    misses = []
    for q, res in zip(answerable, found):
        ranking = res.get("ranking", [])[:10]
        rank = next((i for i, c in enumerate(ranking, 1) if _is_hit(c, q)), None)
        if rank:
            hits += 1
            rr_sum += 1 / rank
        else:
            misses.append(q)

    n = max(len(answerable), 1)
    return {"hit@10": round(hits / n, 3), "mrr@10": round(rr_sum / n, 3)}, misses
