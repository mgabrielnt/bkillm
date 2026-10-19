"""Stage 3 - layered cleaning and de-duplication.

Order: line heuristics -> cross-document frequency filter (PDFs: per-document header/footer filter)
-> Unicode normalisation -> exact + near-duplicate removal -> drop documents under 50 words.

Modules:
  filters.py  boilerplate line patterns and frequency filters
  dedup.py    exact and MinHash near-duplicate removal
"""
from __future__ import annotations

from ...core.utils import normalize_text
from .dedup import dedup
from .filters import frequency_filter, line_filter, pdf_header_footer_filter

MIN_WORDS = 50


# Mengembalikan (dokumen bersih dengan field "full_text", statistik, blok paling sering untuk dicek).
def clean_documents(docs: list[dict]) -> tuple[list[dict], dict, list[tuple[str, int]]]:
    stats = {"input": len(docs)}
    md_docs = [d for d in docs if "pages" not in d]
    pdf_docs = [d for d in docs if "pages" in d]
    for d in md_docs:
        d["text"] = line_filter(normalize_text(d["text"]))
    md_docs, report = frequency_filter(md_docs, key="source")
    for d in md_docs:
        d["text"] = normalize_text(d["text"])
        d["full_text"] = d["text"]
    for d in pdf_docs:
        d["pages"] = pdf_header_footer_filter([{**p, "text": normalize_text(p["text"])} for p in d["pages"]])
        d["full_text"] = "\n\n".join(p["text"] for p in d["pages"])
    docs, stats["exact_dups"], stats["near_dups"] = dedup(md_docs + pdf_docs)
    kept = [d for d in docs if len(d["full_text"].split()) >= MIN_WORDS]
    stats["too_short"] = len(docs) - len(kept)
    stats["output"] = len(kept)
    return kept, stats, report


__all__ = ["clean_documents"]
