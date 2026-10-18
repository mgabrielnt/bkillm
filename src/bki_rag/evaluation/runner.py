"""Experiment runner: retrieval metrics per config (the design doc's ladder) and judged answer quality.

A retrieval hit means a chunk of the same document *group* (an English/Indonesian translation pair of a CMS
item counts as one group) appears in the top k.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from ..core import config as C
from ..core.llm import pmap
from ..core.utils import read_jsonl, write_jsonl
from ..generation.answer import RAG
from ..indexing.store import Index, build
from ..retrieval.retriever import RetrievalConfig, Retriever
from .golden import load_golden
from .judge import judge, summarize

PLAIN_INDEX = C.DATA / "index_plain"

# Change one thing at a time.
CONFIGS: dict[str, tuple[Path, RetrievalConfig]] = {
    "vector": (PLAIN_INDEX, RetrievalConfig("vector", bm25=False, rewrite=False)),
    "hybrid": (PLAIN_INDEX, RetrievalConfig("hybrid", bm25=True, rewrite=False)),
    "hybrid_ctx": (C.INDEX_DIR, RetrievalConfig("hybrid_ctx", bm25=True, rewrite=False)),
    "full": (C.INDEX_DIR, RetrievalConfig("full", bm25=True, rewrite=True)),  # production default
    "full_rerank": (C.INDEX_DIR, RetrievalConfig("full_rerank", bm25=True, rewrite=True, rerank=True)),
}


def _first_hit(ranking: list[dict], q: dict) -> int | None:
    for i, c in enumerate(ranking[:50]):
        if c["group_id"] == q["group_id"] or c["url"] in q["urls"]:
            return i + 1
    return None


def retrieval_metrics(rows: list[dict]) -> dict:
    ranks = [r["rank"] for r in rows]
    n = len(ranks) or 1
    m = {f"hit@{k}": round(sum(1 for x in ranks if x and x <= k) / n, 3) for k in (1, 5, 10, 20)}
    m["mrr@20"] = round(sum(1 / x for x in ranks if x and x <= 20) / n, 3)
    return m


def evaluate_retrieval(name: str, retriever: Retriever, cfg: RetrievalConfig, golden: list[dict]) -> tuple[dict, list]:
    answerable = [q for q in golden if q["answerable"]]
    t0 = time.time()
    found = pmap(lambda q: retriever.search(q["question"], None, cfg), answerable, workers=8, desc=f"retrieve[{name}]")
    rows = [{**q, "rank": _first_hit(f["ranking"], q)} for q, f in zip(answerable, found)]
    m = retrieval_metrics(rows)
    m["by_q_lang"] = {lang: retrieval_metrics([r for r in rows if r["q_lang"] == lang]) for lang in ("en", "id")}
    m["cross_lingual"] = retrieval_metrics([r for r in rows if r["q_lang"] != r["source_lang"]])
    m["short_questions"] = retrieval_metrics([r for r in rows if r.get("style") == "short"])
    m["by_type"] = {t: retrieval_metrics([r for r in rows if r["doc_type"] == t])["hit@10"]
                    for t in sorted({r["doc_type"] for r in rows})}
    m["avg_retrieval_s"] = round((time.time() - t0) * 8 / max(len(rows), 1), 2)
    print(f"[eval] {name:12s} hit@1 {m['hit@1']:.3f}  hit@5 {m['hit@5']:.3f}  hit@10 {m['hit@10']:.3f}  "
          f"hit@20 {m['hit@20']:.3f}  mrr {m['mrr@20']:.3f}  cross-lingual hit@10 {m['cross_lingual']['hit@10']:.3f}  "
          f"short-q hit@10 {m['short_questions']['hit@10']:.3f}")
    return m, [r for r in rows if not r["rank"] or r["rank"] > 10]


def evaluate_answers(name: str, rag: RAG, golden: list[dict]) -> tuple[dict, list]:
    results = pmap(lambda q: rag.answer(q["question"]), golden, workers=8, desc=f"answer[{name}]")
    grades = pmap(lambda qr: judge(*qr), list(zip(golden, results)), workers=8, desc="judge")
    details = [{"id": q["id"], "question": q["question"], "answerable": q["answerable"], "reference": q["answer"],
                "answer": r["answer"], "sources": r["sources"], "grade": g, "latency_s": r["timing"]["total_s"]}
               for q, r, g in zip(golden, results, grades)]
    summary = summarize(details)
    print(f"[eval] {name} answers: {summary}")
    return summary, details


def run(config: str = "full", answers: bool = False, limit: int | None = None) -> None:
    golden = load_golden(limit)
    names = list(CONFIGS) if config == "all" else config.split(",")
    if any(CONFIGS[n][0] == PLAIN_INDEX for n in names) and not (PLAIN_INDEX / "meta.json").exists():
        build(list(read_jsonl(C.CHUNKS_FILE)), PLAIN_INDEX, use_context=False)
    C.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    summary: dict = {}
    indexes: dict[Path, Index] = {}
    for name in names:
        path, cfg = CONFIGS[name]
        retriever = Retriever(indexes.setdefault(path, Index(path)))
        metrics, misses = evaluate_retrieval(name, retriever, cfg, golden)
        summary[name] = {"retrieval": metrics}
        write_jsonl(C.RESULTS_DIR / f"{stamp}_{name}_retrieval_misses.jsonl", misses)
        if answers:
            summary[name]["answers"], details = evaluate_answers(name, RAG(retriever, cfg), golden)
            write_jsonl(C.RESULTS_DIR / f"{stamp}_{name}_answers.jsonl", details)
    out = C.RESULTS_DIR / f"{stamp}_summary.json"
    out.write_text(json.dumps({"models": {"chat": C.CHAT_MODEL, "fast": C.FAST_MODEL, "embed": C.EMBED_MODEL},
                               "n_questions": len(golden), "configs": summary}, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(f"[eval] summary -> {out.relative_to(C.ROOT)}")
