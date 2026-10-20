"""Retrieval quality: does the right document show up near the top for each golden question?

A hit means a chunk of the same document *group* (an English/Indonesian translation pair of a CMS item
counts as one group) appears in the top k.
"""
from __future__ import annotations

import time

from ..core.llm import pmap
from ..retrieval.retriever import Retriever


# Peringkat (mulai 1) chunk pertama dari dokumen yang diharapkan, atau None.
def _first_hit(ranking: list[dict], q: dict) -> int | None:
    for i, c in enumerate(ranking[:50]):
        if c["group_id"] == q["group_id"] or c["url"] in q["urls"]:
            return i + 1
    return None


# Hitung hit@1/5/10/20 dan MRR@20 dari daftar pertanyaan yang sudah diberi peringkat.
def retrieval_metrics(rows: list[dict]) -> dict:
    ranks = [r["rank"] for r in rows]
    n = len(ranks) or 1
    m = {f"hit@{k}": round(sum(1 for x in ranks if x and x <= k) / n, 3) for k in (1, 5, 10, 20)}
    m["mrr@20"] = round(sum(1 / x for x in ranks if x and x <= 20) / n, 3)
    return m


# Jalankan pencarian untuk setiap pertanyaan yang bisa dijawab lalu hitung metriknya.
def evaluate_retrieval(retriever: Retriever, golden: list[dict]) -> tuple[dict, list]:
    answerable = [q for q in golden if q["answerable"]]
    t0 = time.time()
    found = pmap(lambda q: retriever.search(q["question"]), answerable, workers=8, desc="retrieve")
    rows = [{**q, "rank": _first_hit(f["ranking"], q)} for q, f in zip(answerable, found)]
    m = retrieval_metrics(rows)
    m["by_q_lang"] = {lang: retrieval_metrics([r for r in rows if r["q_lang"] == lang]) for lang in ("en", "id")}
    m["cross_lingual"] = retrieval_metrics([r for r in rows if r["q_lang"] != r["source_lang"]])
    m["short_questions"] = retrieval_metrics([r for r in rows if r.get("style") == "short"])
    m["by_type"] = {t: retrieval_metrics([r for r in rows if r["doc_type"] == t])["hit@10"]
                    for t in sorted({r["doc_type"] for r in rows})}
    m["avg_retrieval_s"] = round((time.time() - t0) * 8 / max(len(rows), 1), 2)
    print(f"[eval] retrieval  hit@1 {m['hit@1']:.3f}  hit@5 {m['hit@5']:.3f}  hit@10 {m['hit@10']:.3f}  "
          f"hit@20 {m['hit@20']:.3f}  mrr {m['mrr@20']:.3f}  cross-lingual hit@10 {m['cross_lingual']['hit@10']:.3f}  "
          f"short-q hit@10 {m['short_questions']['hit@10']:.3f}")
    return m, [r for r in rows if not r["rank"] or r["rank"] > 10]
