"""Stage 2: LLM-as-judge untuk faithfulness, kebenaran fakta, dan penolakan."""
from __future__ import annotations

from typing import Any
import numpy as np

from ..core.llm import chat_json
from ..prompts import JUDGE_PROMPT
from ..retrieval.restricted import match_restricted


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
        answer=res.get("answer", "")
    )}], reasoning="low")


def _rate(flags: list[bool]) -> float | None:
    return round(sum(flags) / len(flags), 3) if flags else None


def summarize(details: list[dict], total_cost_usd: float = 0.0) -> dict[str, Any]:
    n = len(details)
    if n == 0:
        return {}

    # Soal Rules & Regulations sengaja dialihkan ke halaman login, jadi tidak dinilai sebagai jawaban
    ans_items = [d for d in details if d.get("answerable") and not match_restricted(d["question"])]
    unans_items = [d for d in details if not d.get("answerable")]
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

    # Latensi dan biaya
    latencies = [d.get("latency_s", 0.0) for d in details]

    return {
        "faithfulness": faithfulness,
        "answer_correctness": correctness,
        "negative_rejection": negative_rejection,
        "false_refusal": false_refusal,
        "_latency_p50": round(float(np.percentile(latencies, 50)), 2),
        "_latency_p95": round(float(np.percentile(latencies, 95)), 2),
        "_cost_per_q": round(total_cost_usd / n, 5),
    }
