"""Evaluation runner ringkas: menguji dan menampilkan metrik inti RAG."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ..core import config as C
from ..core.llm import cost_usd, pmap, usage
from ..core.utils import write_jsonl
from ..generation.answer import RAG
from ..retrieval.retriever import Retriever
from .catalog import ANSWERS, RETRIEVAL
from .golden import load_golden
from .judge import judge, summarize
from .retrieval_eval import evaluate_retrieval


def _print_core_table(all_metrics: dict[str, Any]) -> None:
    """Cetak 1 tabel ringkas untuk metrik inti."""
    catalog_all = {**RETRIEVAL, **ANSWERS}
    
    print(f"\n{'=' * 75}")
    print(f"  HASIL EVALUASI INTI RAG")
    print(f"{'=' * 75}")
    print(f"{'Metrik':<30} | {'Hasil':<10} | {'Target':<10} | {'Status':<8}")
    print(f"{'-' * 30}-+-{'-' * 10}-+-{'-' * 10}-+-{'-' * 8}")

    for key, (display_name, _, target, direction) in catalog_all.items():
        val = all_metrics.get(key)
        if val is None:
            continue
        val_str = f"{val:.3f}" if isinstance(val, float) else str(val)
        tgt_str = f"{direction} {target}" if target is not None else "-"
        
        status = "INFO"
        if target is not None and isinstance(val, (int, float)):
            if direction == ">=":
                status = "PASS" if val >= target else "FAIL"
            elif direction == "<=":
                status = "PASS" if val <= target else "FAIL"

        print(f"{display_name:<30} | {val_str:<10} | {tgt_str:<10} | {status:<8}")

    print(f"{'=' * 75}")
    p50, p95 = all_metrics.get("_latency_p50"), all_metrics.get("_latency_p95")
    cost = all_metrics.get("_cost_per_q")
    if p50 is not None or cost is not None:
        print(f"[Info] Waktu respon p50: {p50 or 0}s, p95: {p95 or 0}s | Biaya riil: ${cost or 0:.5f} / pertanyaan")
    print(f"{'=' * 75}\n")


def evaluate_answers(rag: RAG, golden: list[dict]) -> tuple[dict, list]:
    """Jawab pertanyaan golden set dan nilai dengan juri LLM."""
    u_before = usage()
    results = pmap(lambda q: rag.answer(q["question"]), golden, workers=8, desc="answer")
    u_after = usage()
    ans_cost = cost_usd(u_before, u_after)

    grades = pmap(lambda qr: judge(*qr), list(zip(golden, results)), workers=8, desc="judge")
    
    details = []
    for q, r, g in zip(golden, results, grades):
        details.append({
            "id": q.get("id"),
            "question": q["question"],
            "answerable": q.get("answerable", True),
            "reference": q.get("answer", ""),
            "answer": r.get("answer", ""),
            "sources": r.get("sources", []),
            "grade": g,
            "latency_s": r.get("timing", {}).get("total_s", 0.0),
        })

    summary = summarize(details, total_cost_usd=ans_cost)
    return summary, details


def run(
    stage: str = "all",
    limit: int | None = None,
    answers: bool = False,
) -> None:
    """Jalankan evaluasi ringkas RAG."""
    C.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    summary: dict[str, Any] = {
        "timestamp": stamp,
        "models": {"llm": C.LLM_MODEL, "embed": C.EMBED_MODEL},
    }

    run_answers = answers or stage in ("answers", "all")
    all_table_metrics: dict[str, Any] = {}

    # 1. Retrieval
    golden = load_golden(limit)
    summary["n_questions"] = len(golden)
    retriever = Retriever()
    ret_metrics, misses = evaluate_retrieval(retriever, golden)
    summary["retrieval"] = ret_metrics
    all_table_metrics.update(ret_metrics)
    write_jsonl(C.RESULTS_DIR / f"{stamp}_retrieval_misses.jsonl", misses)

    # 2. Answers (jika diminta)
    if run_answers:
        ans_metrics, details = evaluate_answers(RAG(retriever), golden)
        summary["answers"] = ans_metrics
        all_table_metrics.update(ans_metrics)
        write_jsonl(C.RESULTS_DIR / f"{stamp}_answers_details.jsonl", details)

    # Tampilkan 1 tabel terpadu yang ringkas
    _print_core_table(all_table_metrics)

    # Simpan ringkasan
    out_file = C.RESULTS_DIR / f"{stamp}_summary.json"
    out_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[eval] Ringkasan disimpan ke: {out_file.relative_to(C.ROOT)}")
