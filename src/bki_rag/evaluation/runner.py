"""Evaluation runner: retrieval metrics, then answers graded by an LLM judge."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import openai

from ..core import config as C
from ..core.usage import cost_usd, usage
from ..core.utils import pmap, read_jsonl, write_jsonl
from ..generation.answer import RAG
from ..retrieval.retriever import Retriever
from .golden import load_golden
from .guard import Guard, api_error_msg
from .judge import judge, summarize
from .report import print_core_table, report_incomplete, save_summary
from .retrieval_eval import evaluate_retrieval


# Nilai ulang soal yang belum punya nilai juri (jawaban sudah ada di detail).
def _grade(details: list[dict], guard: Guard) -> None:
    # Hanya soal yang sudah terjawab tapi belum punya nilai juri yang sah
    todo = [d for d in details if not d.get("error") and (not d.get("grade") or d["grade"].get("error"))]
    grades = pmap(lambda d: guard(judge, d, {"answer": d["answer"], "chunks": d.get("chunks", [])}),
                  todo, workers=8, desc="judge")
    for d, g in zip(todo, grades):
        d["grade"] = g


# Tahap 2: bot menjawab semua soal, juri menilai, lalu metrik dihitung. Kembalikan (metrik, detail per soal).
# Detail menyimpan teks chunk agar --rejudge bisa menilai ulang tanpa menjawab ulang.
def evaluate_answers(rag: RAG, golden: list[dict], guard: Guard, workers: int = 8) -> tuple[dict, list]:
    u_before = usage()
    results = pmap(lambda q: guard(rag.answer, q["question"]), golden, workers=workers, desc="answer")
    u_after = usage()
    ans_cost = cost_usd(u_before, u_after)

    # Satu baris detail per soal: data golden, jawaban bot, chunk sumber, dan waktu respon
    details = []
    for q, r in zip(golden, results):
        details.append({
            "id": q.get("id"),
            "question": q["question"],
            "answerable": q.get("answerable", True),
            "reference": q.get("answer", ""),
            "answer": r.get("answer", ""),
            "error": r.get("error"),
            "sources": r.get("sources", []),
            "chunks": [{k: c.get(k, "") for k in ("title", "url", "text")} for c in r.get("chunks", [])],
            "timing": r.get("timing", {}),
        })
    _grade(details, guard)

    summary = summarize(details, total_cost_usd=ans_cost)
    return summary, details


# Lanjutkan run yang terputus: nilai hanya soal yang belum dinilai di file *_answers_details.jsonl,
# lalu hitung ulang metrik dan timpa file detail serta ringkasannya.
def rejudge(path: str) -> None:
    details_file = Path(path) if Path(path).is_absolute() else C.ROOT / path
    details = list(read_jsonl(details_file))
    guard = Guard()
    _grade(details, guard)
    write_jsonl(details_file, details)

    summary_file = details_file.with_name(details_file.name.replace("_answers_details.jsonl", "_summary.json"))
    summary = json.loads(summary_file.read_text(encoding="utf-8")) if summary_file.exists() else {}
    # Biaya menjawab diambil dari ringkasan lama (penilaian ulang tidak menjawab ulang)
    old_cost = summary.get("answers", {}).get("_cost_per_q", 0.0) * len(details)
    summary["answers"] = summarize(details, total_cost_usd=old_cost)
    print_core_table({**summary.get("retrieval", {}), **summary["answers"]})
    report_incomplete(details, details_file, guard)
    save_summary(summary, summary.get("timestamp") or details_file.name.split("_")[0])


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
