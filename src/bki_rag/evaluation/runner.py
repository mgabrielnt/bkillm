"""Evaluation runner ringkas: menguji dan menampilkan metrik inti RAG."""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import openai

from ..core import config as C
from ..core.llm import cost_usd, pmap, usage
from ..core.utils import read_jsonl, write_jsonl
from ..generation.answer import RAG
from ..retrieval.retriever import Retriever
from .catalog import ANSWERS, RETRIEVAL
from .golden import load_golden
from .judge import judge, summarize
from .retrieval_eval import evaluate_retrieval


# Pesan singkat untuk error API: apa yang terjadi dan apa yang harus dilakukan.
def _api_error_msg(exc: Exception) -> str:
    text = str(exc).lower()
    if "budget" in text or "quota" in text or "insufficient" in text:
        return "Saldo/budget API habis. Naikkan budget API key (atau tunggu reset), lalu jalankan lagi."
    if isinstance(exc, openai.AuthenticationError):
        return "API key ditolak. Periksa OPENAI_API_KEY di .env."
    if isinstance(exc, openai.APIConnectionError):
        return "Tidak bisa terhubung ke layanan AI. Periksa internet / OPENAI_BASE_URL."
    return f"{type(exc).__name__}: {str(exc)[:200]}"


# Pembungkus panggilan API per soal: error dicatat sebagai {"error": pesan} agar evaluasi tidak berhenti,
# dan begitu budget habis / API key ditolak, soal berikutnya langsung dilewati tanpa memanggil API.
class _Guard:
    # stop: tanda budget habis; reason: pesan penyebabnya.
    def __init__(self) -> None:
        self.stop = threading.Event()
        self.reason = ""

    # Jalankan fn(*args); jika API error, kembalikan {"error": pesan} alih-alih melempar exception.
    def __call__(self, fn: Callable[..., dict], *args) -> dict:
        if self.stop.is_set():
            return {"error": self.reason}
        try:
            return fn(*args)
        except openai.APIError as exc:
            msg = _api_error_msg(exc)
            if "budget" in msg.lower() or isinstance(exc, openai.AuthenticationError):
                self.reason = msg
                self.stop.set()
            return {"error": msg}


# Cetak tabel metrik (hasil, target, PASS/FAIL dari catalog) lalu baris info latency dan biaya.
def _print_core_table(all_metrics: dict[str, Any]) -> None:
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

        # PASS/FAIL sesuai arah target: ">=" makin tinggi makin baik, "<=" makin rendah makin baik
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


# Nilai ulang soal yang belum punya nilai juri (jawaban sudah ada di detail).
def _grade(details: list[dict], guard: _Guard) -> None:
    # Hanya soal yang sudah terjawab tapi belum punya nilai juri yang sah
    todo = [d for d in details if not d.get("error") and (not d.get("grade") or d["grade"].get("error"))]
    res = lambda d: {"answer": d["answer"], "chunks": d.get("chunks", [])}
    grades = pmap(lambda d: guard(judge, d, res(d)), todo, workers=8, desc="judge")
    for d, g in zip(todo, grades):
        d["grade"] = g


# Tahap 2: bot menjawab semua soal, juri menilai, lalu metrik dihitung. Kembalikan (metrik, detail per soal).
# Detail menyimpan teks chunk agar --rejudge bisa menilai ulang tanpa menjawab ulang.
def evaluate_answers(rag: RAG, golden: list[dict], guard: _Guard) -> tuple[dict, list]:
    u_before = usage()
    results = pmap(lambda q: guard(rag.answer, q["question"]), golden, workers=8, desc="answer")
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
            "latency_s": r.get("timing", {}).get("total_s", 0.0),
        })
    _grade(details, guard)

    summary = summarize(details, total_cost_usd=ans_cost)
    return summary, details


# Laporkan soal yang gagal dijawab/dinilai dan cara melanjutkannya tanpa membayar ulang jawaban.
def _report_incomplete(details: list[dict], details_file: Path, guard: _Guard) -> None:
    no_answer = sum(1 for d in details if d.get("error"))
    no_grade = sum(1 for d in details if not d.get("error") and d.get("grade", {}).get("error"))
    if not (no_answer or no_grade):
        return
    print(f"[eval] PERHATIAN: {no_answer} soal gagal dijawab, {no_grade} soal belum dinilai juri. "
          f"Metrik di atas hanya dari soal yang lengkap.")
    if guard.reason:
        print(f"[eval] Penyebab: {guard.reason}")
    if no_grade and not no_answer:
        print(f"[eval] Lanjutkan penilaian saja: python -m bki_rag eval --rejudge {details_file.relative_to(C.ROOT)}")


# Simpan ringkasan metrik ke data/eval/results/<stamp>_summary.json.
def _save_summary(summary: dict, stamp: str) -> None:
    out_file = C.RESULTS_DIR / f"{stamp}_summary.json"
    out_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[eval] Ringkasan disimpan ke: {out_file.relative_to(C.ROOT)}")


# Lanjutkan run yang terputus: nilai hanya soal yang belum dinilai di file *_answers_details.jsonl,
# lalu hitung ulang metrik dan timpa file detail serta ringkasannya.
def rejudge(path: str) -> None:
    details_file = Path(path) if Path(path).is_absolute() else C.ROOT / path
    details = list(read_jsonl(details_file))
    guard = _Guard()
    _grade(details, guard)
    write_jsonl(details_file, details)

    summary_file = details_file.with_name(details_file.name.replace("_answers_details.jsonl", "_summary.json"))
    summary = json.loads(summary_file.read_text(encoding="utf-8")) if summary_file.exists() else {}
    # Biaya menjawab diambil dari ringkasan lama (penilaian ulang tidak menjawab ulang)
    old_cost = summary.get("answers", {}).get("_cost_per_q", 0.0) * len(details)
    summary["answers"] = summarize(details, total_cost_usd=old_cost)
    _print_core_table({**summary.get("retrieval", {}), **summary["answers"]})
    _report_incomplete(details, details_file, guard)
    _save_summary(summary, summary.get("timestamp") or details_file.name.split("_")[0])


# Perintah `eval`: retrieval (Tahap 1), lalu jawaban + juri (Tahap 2), cetak tabel, simpan hasil ke data/eval/results/.
def run(
    stage: str = "all",
    limit: int | None = None,
    answers: bool = False,
) -> None:
    C.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    summary: dict[str, Any] = {
        "timestamp": stamp,
        "models": {"llm": C.LLM_MODEL, "embed": C.EMBED_MODEL},
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
        print(f"[eval] Berhenti di tahap retrieval. {_api_error_msg(exc)}")
        return
    summary["retrieval"] = ret_metrics
    all_table_metrics.update(ret_metrics)
    write_jsonl(C.RESULTS_DIR / f"{stamp}_retrieval_misses.jsonl", misses)

    # 2. Answers (jika diminta); error per soal dicatat, tidak menghentikan evaluasi
    guard = _Guard()
    details_file = C.RESULTS_DIR / f"{stamp}_answers_details.jsonl"
    if run_answers:
        ans_metrics, details = evaluate_answers(RAG(retriever), golden, guard)
        summary["answers"] = ans_metrics
        all_table_metrics.update(ans_metrics)
        write_jsonl(details_file, details)

    # Tampilkan 1 tabel terpadu yang ringkas
    _print_core_table(all_table_metrics)
    if run_answers:
        _report_incomplete(details, details_file, guard)
    _save_summary(summary, stamp)
