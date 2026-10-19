"""Optional listwise LLM reranker.

Off by default: in our evaluation the FAST_MODEL reranker lowered answer accuracy (0.888 vs 0.913) and added
~2 s per question, because hybrid search + contextual retrieval already puts the right chunk in the top 10
for ~98% of questions. Enable it with RetrievalConfig(rerank=True) / eval config "full_rerank".
"""
from __future__ import annotations

from ..core.llm import chat_json
from ..prompts import RERANK_PROMPT


# Beri skor 0-10 untuk setiap kandidat dengan model cepat, lalu urutkan dari yang terbaik.
def rerank(question: str, candidates: list[dict]) -> list[tuple[dict, float]]:
    passages = "\n\n".join(
        f'<passage id="{i}" title="{c["title"]}" date="{(c.get("published_at") or "")[:10]}">\n'
        f'{c["text"][:1400]}\n</passage>' for i, c in enumerate(candidates))
    res = chat_json([{"role": "user", "content": RERANK_PROMPT.format(question=question, passages=passages)}])
    scores = res.get("scores", {}) if isinstance(res, dict) else {}
    ranked = []
    for i, c in enumerate(candidates):
        try:
            s = float(scores.get(str(i), 0))
        except (TypeError, ValueError):
            s = 0.0
        ranked.append((c, s - i * 1e-3))  # jika skor sama, pakai urutan hasil gabungan
    ranked.sort(key=lambda x: -x[1])
    return ranked
