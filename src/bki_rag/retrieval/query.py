"""Query understanding: standalone question (chat history resolved) + English/Indonesian variants + keywords."""
from __future__ import annotations

import re

from langdetect import detect

from ..core.llm import chat_json
from ..prompts import REWRITE_PROMPT

# Kata yang hampir pasti Bahasa Indonesia. Pertanyaan pendek seperti "Apa itu Port State Control?" berisi istilah
# Inggris, sehingga langdetect saja menebaknya sebagai Inggris dan jawaban keluar dalam bahasa yang salah.
ID_MARKERS = frozenset("""apa itu ini yang dan berapa siapa bagaimana kapan dimana mengapa kenapa adalah saja untuk
dengan dari apakah bisa pada atau tidak saya kami di oleh sebagai agar jelaskan sebutkan""".split())


# Deteksi bahasa pertanyaan: 'id' atau 'en' (bahasa Inggris jika ragu).
def detect_lang(text: str) -> str:
    if ID_MARKERS & set(re.findall(r"[a-z]+", text.lower())):
        return "id"
    try:
        return "id" if detect(text) in ("id", "ms") else "en"
    except Exception:
        return "en"


# Pertanyaan tanpa riwayat dicari apa adanya, tanpa memanggil model; bahasanya dideteksi secara lokal.
def plain_query(question: str) -> dict:
    return {"standalone": question, "lang": detect_lang(question)}


# Mengembalikan {"standalone", "en", "id", "keywords", "lang"}; aman jika JSON dari model rusak.
def rewrite_query(question: str, history: list[dict] | None = None) -> dict:
    hist = "\n".join(f"{m['role']}: {m['content'][:600]}" for m in (history or [])[-6:]) or "(none)"
    out = chat_json([{"role": "user", "content": REWRITE_PROMPT.format(history=hist, question=question)}])
    out.setdefault("standalone", question)
    if out.get("lang") not in ("en", "id"):
        out["lang"] = detect_lang(question)
    return out
