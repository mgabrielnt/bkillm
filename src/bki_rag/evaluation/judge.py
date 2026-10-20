"""LLM-as-judge for answer quality: correctness vs reference, faithfulness to sources, citations, refusals."""
from __future__ import annotations

from ..core import config as C
from ..core.llm import chat_json
from ..prompts import JUDGE_PROMPT


# Nilai satu jawaban chatbot terhadap jawaban acuan dan sumber yang diberikan kepadanya.
def judge(q: dict, res: dict) -> dict:
    # Juri melihat persis yang dilihat chatbot (chunk lengkap, konteks, tanggal), agar tidak salah menilai.
    sources = "\n\n".join(f"[{i}] {c['title']} ({c['url']}) date={(c.get('published_at') or '')[:10]}\n"
                          f"context: {c.get('context', '')}\n{c['text']}" for i, c in enumerate(res["chunks"], 1))
    return chat_json([{"role": "user", "content": JUDGE_PROMPT.format(
        question=q["question"], answerable=q["answerable"], reference=q["answer"] or "(none: should refuse)",
        sources=sources, answer=res["answer"])}], reasoning="low")


# Rata-ratakan nilai menjadi metrik ringkasan.
def summarize(details: list[dict]) -> dict:
    ans = [d for d in details if d["answerable"]]
    una = [d for d in details if not d["answerable"]]

    # Rata-rata sebuah nilai angka.
    def avg(rows: list[dict], key: str) -> float:
        return round(sum(float(r["grade"].get(key, 0) or 0) for r in rows) / max(len(rows), 1), 3)

    # Persentase baris yang nilai benar/salahnya bernilai benar.
    def rate(rows: list[dict], key: str) -> float:
        return round(sum(1 for r in rows if r["grade"].get(key)) / max(len(rows), 1), 3)

    return {"correct": avg(ans, "correct"), "faithful": avg(details, "faithful"), "cited": avg(ans, "cited"),
            "false_refusal_rate": rate(ans, "refused"), "unanswerable_refused": rate(una, "refused"),
            "same_language": rate(details, "same_language"),
            "avg_latency_s": round(sum(d["latency_s"] for d in details) / max(len(details), 1), 2)}
