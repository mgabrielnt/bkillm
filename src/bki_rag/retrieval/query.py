"""Query understanding: standalone question (chat history resolved) + English/Indonesian variants + keywords."""
from __future__ import annotations

from ..core.llm import chat_json
from ..prompts import REWRITE_PROMPT


# Deteksi bahasa pertanyaan: 'id' atau 'en' (bahasa Inggris jika ragu).
def detect_lang(text: str) -> str:
    from langdetect import detect
    try:
        return "id" if detect(text) in ("id", "ms") else "en"
    except Exception:
        return "en"


# Mengembalikan {"standalone", "en", "id", "keywords", "lang"}; aman jika JSON dari model rusak.
def rewrite_query(question: str, history: list[dict] | None = None) -> dict:
    hist = "\n".join(f"{m['role']}: {m['content'][:600]}" for m in (history or [])[-6:]) or "(none)"
    out = chat_json([{"role": "user", "content": REWRITE_PROMPT.format(history=hist, question=question)}])
    out.setdefault("standalone", question)
    if out.get("lang") not in ("en", "id"):
        out["lang"] = detect_lang(question)
    return out
