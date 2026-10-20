"""Evaluation run (`python -m bki_rag eval`): retrieval metrics and, optionally, judged answers.

Writes data/eval/results/<time>_summary.json plus the retrieval misses and (with --answers) every answer.
"""
from __future__ import annotations

import json
from datetime import datetime

from ..core import config as C
from ..core.llm import pmap
from ..core.utils import write_jsonl
from ..generation.answer import RAG
from ..retrieval.retriever import Retriever
from .golden import load_golden
from .judge import judge, summarize
from .retrieval_eval import evaluate_retrieval


# Jawab setiap pertanyaan golden set lalu minta juri menilainya.
def evaluate_answers(rag: RAG, golden: list[dict]) -> tuple[dict, list]:
    results = pmap(lambda q: rag.answer(q["question"]), golden, workers=8, desc="answer")
    grades = pmap(lambda qr: judge(*qr), list(zip(golden, results)), workers=8, desc="judge")
    details = [{"id": q["id"], "question": q["question"], "answerable": q["answerable"], "reference": q["answer"],
                "answer": r["answer"], "sources": r["sources"], "grade": g, "latency_s": r["timing"]["total_s"]}
               for q, r, g in zip(golden, results, grades)]
    summary = summarize(details)
    print(f"[eval] answers: {summary}")
    return summary, details


# Evaluasi pencarian (dan jawaban jika answers=True), lalu tulis ringkasannya ke data/eval/results/.
def run(answers: bool = False, limit: int | None = None) -> None:
    golden = load_golden(limit)
    C.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    retriever = Retriever()
    metrics, misses = evaluate_retrieval(retriever, golden)
    summary: dict = {"retrieval": metrics}
    write_jsonl(C.RESULTS_DIR / f"{stamp}_retrieval_misses.jsonl", misses)
    if answers:
        summary["answers"], details = evaluate_answers(RAG(retriever), golden)
        write_jsonl(C.RESULTS_DIR / f"{stamp}_answers.jsonl", details)
    out = C.RESULTS_DIR / f"{stamp}_summary.json"
    out.write_text(json.dumps({"models": {"llm": C.LLM_MODEL, "embed": C.EMBED_MODEL}, "n_questions": len(golden),
                               **summary}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"[eval] summary -> {out.relative_to(C.ROOT)}")
