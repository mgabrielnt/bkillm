"""LLM-as-judge for answer quality: correctness vs reference, faithfulness to sources, citations, refusals."""
from __future__ import annotations

from ..core import config as C
from ..core.llm import chat_json
from ..prompts import JUDGE_PROMPT


def judge(q: dict, res: dict) -> dict:
    # The judge sees exactly what the chatbot saw (full chunk, context and date), or it flags supported claims.
    """Grade one chatbot answer against the reference and the sources it was given."""
    sources = "\n\n".join(f"[{i}] {c['title']} ({c['url']}) date={(c.get('published_at') or '')[:10]}\n"
                          f"context: {c.get('context', '')}\n{c['text']}" for i, c in enumerate(res["chunks"], 1))
    return chat_json([{"role": "user", "content": JUDGE_PROMPT.format(
        question=q["question"], answerable=q["answerable"], reference=q["answer"] or "(none: should refuse)",
        sources=sources, answer=res["answer"])}], model=C.JUDGE_MODEL, reasoning="low")


def summarize(details: list[dict]) -> dict:
    """Average the grades into the summary metrics."""
    ans = [d for d in details if d["answerable"]]
    una = [d for d in details if not d["answerable"]]

    def avg(rows: list[dict], key: str) -> float:
        """Mean of a numeric grade field."""
        return round(sum(float(r["grade"].get(key, 0) or 0) for r in rows) / max(len(rows), 1), 3)

    def rate(rows: list[dict], key: str) -> float:
        """Share of rows where a grade flag is true."""
        return round(sum(1 for r in rows if r["grade"].get(key)) / max(len(rows), 1), 3)

    return {"correct": avg(ans, "correct"), "faithful": avg(details, "faithful"), "cited": avg(ans, "cited"),
            "false_refusal_rate": rate(ans, "refused"), "unanswerable_refused": rate(una, "refused"),
            "same_language": rate(details, "same_language"),
            "avg_latency_s": round(sum(d["latency_s"] for d in details) / max(len(details), 1), 2)}
