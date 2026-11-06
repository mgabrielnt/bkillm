"""Evaluation runner: retrieval metrics, then answers graded by an LLM judge."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import openai

from ..core import config as C
from ..core.usage import cost_usd, usage
from ..core.utils import write_jsonl
from ..generation.answer import RAG
from ..retrieval.retriever import Retriever
from .golden import load_golden
from .answer_eval import evaluate_answers
from .guard import Guard, api_error_msg
from .report import print_core_table, report_incomplete, save_summary
from .retrieval_eval import evaluate_retrieval


# Perintah `eval`: retrieval (Tahap 1), lalu jawaban + juri (Tahap 2), cetak tabel, simpan hasil ke data/eval/results/.
def run(
    stage: str = "all",
    limit: int | None = None,
    answers: bool = False,
    workers: int = 8,
) -> None:
    C.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    u_start = usage()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    summary: dict[str, Any] = {
        "timestamp": stamp,
        "models": {"llm": C.LLM_MODEL, "embed": C.EMBED_MODEL},
        "settings": {"answer_reasoning": C.ANSWER_REASONING, "answer_verbosity": C.ANSWER_VERBOSITY,
                     "stream_answer": C.STREAM_ANSWER, "workers": workers},
    }

    run_answers = answers or stage in ("answers", "all")
    all_table_metrics: dict[str, Any] = {}

    # 1. Retrieval (tanpa hasil retrieval yang lengkap evaluasi tidak berarti, jadi berhenti dengan pesan)
    golden = load_golden(limit)
    summary["n_questions"] = len(golden)
    retriever = Retriever()
    try:
        ret_metrics, misses = evaluate_retrieval(retriever, golden)
    except openai.APIError as exc:
        print(f"[eval] Berhenti di tahap retrieval. {api_error_msg(exc)}")
        return
    summary["retrieval"] = ret_metrics
    all_table_metrics.update(ret_metrics)
    write_jsonl(C.RESULTS_DIR / f"{stamp}_retrieval_misses.jsonl", misses)

    # 2. Answers (jika diminta); error per soal dicatat, tidak menghentikan evaluasi
    guard = Guard()
    details_file = C.RESULTS_DIR / f"{stamp}_answers_details.jsonl"
    if run_answers:
        ans_metrics, details = evaluate_answers(RAG(retriever), golden, guard, workers)
        summary["answers"] = ans_metrics
        all_table_metrics.update(ans_metrics)
        write_jsonl(details_file, details)

    # Tampilkan 1 tabel terpadu yang ringkas
    print_core_table(all_table_metrics)
    if run_answers:
        report_incomplete(details, details_file, guard)
    summary["cost_total_usd"] = round(cost_usd(u_start, usage()), 5)
    print(f"[eval] Total biaya API run ini: ${summary['cost_total_usd']:.4f}")
    save_summary(summary, stamp)
