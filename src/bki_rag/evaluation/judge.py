"""Stage 2: LLM-as-judge untuk faithfulness, kebenaran fakta, dan penolakan."""
from __future__ import annotations

import re
from typing import Any
import numpy as np

from ..core.llm import chat_json
from ..prompts import JUDGE_PROMPT
from ..retrieval.restricted import match_restricted


# Minta juri gpt-5-nano menilai satu jawaban: kirim soal, kunci jawaban, 10 chunk sumber, dan jawaban bot.
# Kembalikan {"refused": bool, "faithful": 0/1, "correct": 0/0.5/1, "note": alasan singkat}.
def judge(q: dict, res: dict) -> dict[str, Any]:
    sources = "\n\n".join(
        f"[{i}] {c.get('title', '')} ({c.get('url', '')})\n{c.get('text', '')}"
        for i, c in enumerate(res.get("chunks", []), 1)
    )
    return chat_json([{"role": "user", "content": JUDGE_PROMPT.format(
        question=q["question"],
        answerable=q.get("answerable", True),
        reference=q.get("answer") or "(none)",
        sources=sources or "(no sources)",
        answer=re.sub(r"\[\d+\]", "", res.get("answer", ""))  # nomor sudah diurut ulang, tidak cocok dengan daftar ini
    )}], reasoning="low")


STAGES = ("rewrite", "embed", "search", "first_text", "answer", "total")


# Proporsi nilai True dalam daftar (dibulatkan 3 desimal); None jika daftarnya kosong.
def _rate(flags: list[bool]) -> float | None:
    return round(sum(flags) / len(flags), 3) if flags else None


# Tahap 2: ubah nilai juri semua soal menjadi metrik (faithfulness, correctness, penolakan, latency, biaya).
# Soal yang gagal dijawab atau belum dinilai tidak dihitung; jumlahnya dilaporkan di n_ungraded.
def summarize(details: list[dict], total_cost_usd: float = 0.0) -> dict[str, Any]:
    answered = [d for d in details if not d.get("error")]
    graded = [d for d in answered if d.get("grade") and not d["grade"].get("error")]
    n = len(details)
    if not graded:
        return {"n_ungraded": n}

    # Soal Rules & Regulations sengaja dialihkan ke halaman login, jadi tidak dinilai sebagai jawaban
    ans_items = [d for d in graded if d.get("answerable") and not match_restricted(d["question"])]
    unans_items = [d for d in graded if not d.get("answerable")]
    refused = lambda d: bool(d.get("grade", {}).get("refused"))
    non_refused = [d for d in ans_items if not refused(d)]

    # 1. Faithfulness (bebas halusinasi), hanya jawaban yang berisi klaim
    faithful_scores = [float(d.get("grade", {}).get("faithful", 0)) for d in non_refused]
    faithfulness = round(float(np.mean(faithful_scores)), 3) if faithful_scores else None

    # 2. Kebenaran fakta vs acuan (menolak soal yang bisa dijawab = 0)
    correct_scores = [float(d.get("grade", {}).get("correct", 0)) for d in ans_items]
    correctness = round(float(np.mean(correct_scores)), 3) if correct_scores else None

    # 3. Soal jebakan yang ditolak, dan soal valid yang keliru ditolak
    negative_rejection = _rate([refused(d) for d in unans_items])
    false_refusal = _rate([refused(d) for d in ans_items])

    # Latensi tiap tahap (soal yang langsung ke halaman login tidak memanggil model, jadi tidak dihitung)
    timed = [d["timing"] for d in answered if d.get("timing", {}).get("first_text_s") is not None]
    stages: dict[str, float] = {}
    for stage in STAGES:
        values = [t[f"{stage}_s"] for t in timed if f"{stage}_s" in t]
        if values:
            stages[f"_{stage}_p50"] = round(float(np.percentile(values, 50)), 3)
            stages[f"_{stage}_p95"] = round(float(np.percentile(values, 95)), 3)

    return {
        **stages,
        "faithfulness": faithfulness,
        "answer_correctness": correctness,
        "negative_rejection": negative_rejection,
        "false_refusal": false_refusal,
        "_cost_per_q": round(total_cost_usd / n, 5),
        "n_ungraded": n - len(graded),
    }
