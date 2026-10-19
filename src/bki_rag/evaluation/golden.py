"""Golden test set: LLM-drafted questions from stratified random chunks + hand-written unanswerable ones.

About half the questions are asked in the other language than their source (cross-lingual retrieval) and
60% are short, casual chat-style questions; the rest are detailed and self-contained.
"""
from __future__ import annotations

import random
from collections import defaultdict

from ..core import config as C
from ..core.llm import chat_json, pmap
from ..core.utils import read_jsonl, write_jsonl
from ..prompts import GOLDEN_PROMPT, GOLDEN_STYLES

STRATA = {  # doc_type -> number of questions
    "service": 20, "company": 10, "esg": 14, "news": 16, "announcement": 4, "annual_report": 18,
    "sustainability_report": 10, "article": 4, "research": 2, "job": 2, "policy": 2, "event": 1,
}

# Must be refused: plausible-but-absent BKI facts and off-topic requests.
UNANSWERABLE = [
    "Berapa tarif survei klasifikasi untuk kapal tanker 5000 GT di BKI?",
    "Siapa nama direktur utama BKI pada tahun 1985?",
    "Apakah BKI menyediakan layanan sertifikasi kelaikan pesawat terbang komersial?",
    "Berapa harga saham BKI di Bursa Efek Indonesia hari ini?",
    "What will BKI's total revenue be in 2030?",
    "Bagaimana cara memasak rendang yang empuk?",
    "Who won the 2022 FIFA World Cup?",
    "Berapa gaji pokok surveyor junior di BKI?",
    "What is the Wi-Fi password at the BKI head office?",
    "Berapa jumlah kapal yang diklasifikasikan BKI pada tahun 1990?",
    "What is the phone number of BKI's representative office in Tokyo?",
    "Tuliskan kode Python untuk mengurutkan sebuah list.",
    "What is today's USD to IDR exchange rate?",
    "Kapan BKI membuka lowongan untuk posisi pilot helikopter?",
    "What hull thickness do BKI rules require for spacecraft?",
    "Siapa juara Piala Dunia 2026?",
    "What discount does BKI give to Gold loyalty program members?",
    "Berapa nomor WhatsApp pribadi direktur keuangan BKI?",
    "Apakah BKI pernah mengklasifikasi kapal Titanic?",
    "Which hotel does BKI recommend for visiting auditors in Surabaya?",
]
_ID_WORDS = ("berapa", "apakah", "siapa", "bagaimana", "kapan", "tuliskan")


def build_golden() -> None:
    """Draft the golden test set from stratified random chunks into data/eval/golden.jsonl."""
    rng = random.Random(42)
    by_type: dict[str, list[dict]] = defaultdict(list)
    for c in read_jsonl(C.CHUNKS_FILE):
        if c["tokens"] >= 120:
            by_type[c["doc_type"]].append(c)
    picks = []
    for t, k in STRATA.items():
        pool = by_type.get(t, [])
        picks += rng.sample(pool, min(len(pool), k + 4))  # spare picks for unsuitable passages
    tasks = [(c, "Indonesian" if rng.random() < 0.5 else "English", "short" if rng.random() < 0.6 else "detailed")
             for c in picks]

    def draft(task):
        """Ask the judge model for one question + reference answer about this chunk."""
        c, qlang, style = task
        return chat_json([{"role": "user", "content": GOLDEN_PROMPT.format(
            title=c["title"], doc_type=c["doc_type"], date=(c.get("published_at") or "")[:10],
            text=c["text"][:6000], qlang=qlang, style=GOLDEN_STYLES[style])}], model=C.JUDGE_MODEL, reasoning="low")

    rows, per_type = [], defaultdict(int)
    for (c, qlang, style), r in zip(tasks, pmap(draft, tasks, desc="golden")):
        if not r.get("suitable") or not r.get("question") or per_type[c["doc_type"]] >= STRATA[c["doc_type"]]:
            continue
        per_type[c["doc_type"]] += 1
        rows.append({"id": f"q{len(rows) + 1:03d}", "question": r["question"], "answer": r.get("answer", ""),
                     "answerable": True, "style": style, "doc_type": c["doc_type"],
                     "q_lang": "id" if qlang == "Indonesian" else "en", "source_lang": c["lang"],
                     "chunk_id": c["chunk_id"], "group_id": c["group_id"], "urls": [c["url"]] + c.get("aliases", [])})
    for q in UNANSWERABLE:
        rows.append({"id": f"u{len(rows) + 1:03d}", "question": q, "answer": "", "answerable": False,
                     "doc_type": "none", "q_lang": "id" if any(w in q.lower() for w in _ID_WORDS) else "en",
                     "source_lang": None, "chunk_id": None, "group_id": None, "urls": []})
    write_jsonl(C.GOLDEN_FILE, rows)
    print(f"[golden] {len(rows)} questions -> {C.GOLDEN_FILE.relative_to(C.ROOT)} ({dict(per_type)}, "
          f"{len(UNANSWERABLE)} unanswerable)")


def load_golden(limit: int | None = None) -> list[dict]:
    """The golden set, or an evenly spread sample of it (keeps the answerable/unanswerable mix)."""
    rows = list(read_jsonl(C.GOLDEN_FILE))
    if not limit or limit >= len(rows):
        return rows
    step = len(rows) / limit
    return [rows[int(i * step)] for i in range(limit)]
