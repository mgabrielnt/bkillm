"""Experiment runner: retrieval metrics per configuration (the design doc's ladder) and judged answers.

Writes data/eval/results/<time>_summary.json plus per-config misses / answers files.
"""
from __future__ import annotations

import json
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
from .retrieval_eval import evaluate_retrieval

PLAIN_INDEX = C.DATA / "index_plain"

# Change one thing at a time.
CONFIGS: dict[str, tuple[Path, RetrievalConfig]] = {
    "vector": (PLAIN_INDEX, RetrievalConfig("vector", bm25=False, rewrite=False)),
    "hybrid": (PLAIN_INDEX, RetrievalConfig("hybrid", bm25=True, rewrite=False)),
    "hybrid_ctx": (C.INDEX_DIR, RetrievalConfig("hybrid_ctx", bm25=True, rewrite=False)),
    "full": (C.INDEX_DIR, RetrievalConfig("full", bm25=True, rewrite=True)),  # production default
    "full_rerank": (C.INDEX_DIR, RetrievalConfig("full_rerank", bm25=True, rewrite=True, rerank=True)),
}


def evaluate_answers(name: str, rag: RAG, golden: list[dict]) -> tuple[dict, list]:
    """Answer every golden question and let the judge grade it."""
    results = pmap(lambda q: rag.answer(q["question"]), golden, workers=8, desc=f"answer[{name}]")
    grades = pmap(lambda qr: judge(*qr), list(zip(golden, results)), workers=8, desc="judge")
    details = [{"id": q["id"], "question": q["question"], "answerable": q["answerable"], "reference": q["answer"],
                "answer": r["answer"], "sources": r["sources"], "grade": g, "latency_s": r["timing"]["total_s"]}
               for q, r, g in zip(golden, results, grades)]
    summary = summarize(details)
    print(f"[eval] {name} answers: {summary}")
    return summary, details


def run(config: str = "full", answers: bool = False, limit: int | None = None) -> None:
    """Evaluate the chosen configurations and write a summary to data/eval/results/."""
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
