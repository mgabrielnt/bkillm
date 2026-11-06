"""Print and save the evaluation results: metrics table, incomplete-run notice, summary file."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..core import config as C
from .catalog import ANSWERS, RETRIEVAL
from .guard import Guard
from .judge import STAGES


# Cetak tabel metrik (hasil, target, PASS/FAIL dari catalog) lalu baris info latency dan biaya.
def print_core_table(all_metrics: dict[str, Any]) -> None:
    catalog_all = {**RETRIEVAL, **ANSWERS}

    print(f"\n{'=' * 75}")
    print("  HASIL EVALUASI INTI RAG")
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
    for stage in STAGES:
        p50, p95 = all_metrics.get(f"_{stage}_p50"), all_metrics.get(f"_{stage}_p95")
        if p50 is not None:
            print(f"[Waktu] {stage:<11} p50 {p50:>6.2f}s | p95 {p95:>6.2f}s")
    cost = all_metrics.get("_cost_per_q")
    if cost is not None:
        print(f"[Info] Biaya menjawab: ${cost:.5f} / pertanyaan")
    print(f"{'=' * 75}\n")


# Laporkan soal yang gagal dijawab/dinilai dan cara melanjutkannya tanpa membayar ulang jawaban.
def report_incomplete(details: list[dict], details_file: Path, guard: Guard) -> None:
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
def save_summary(summary: dict, stamp: str) -> None:
    out_file = C.RESULTS_DIR / f"{stamp}_summary.json"
    out_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[eval] Ringkasan disimpan ke: {out_file.relative_to(C.ROOT)}")
