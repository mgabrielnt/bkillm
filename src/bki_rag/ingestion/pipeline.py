"""Stages 2-4 orchestration: extract -> clean/dedup -> chunk. Re-runnable without re-crawling."""
from __future__ import annotations

import random
from collections import Counter
from urllib.parse import urlparse

from ..core import config as C
from .chunk import chunk_document
from .clean import clean_documents
from .extract import cms_docs, page_docs, pdf_docs
from ..core.utils import count_tokens, sha256, write_jsonl

# Listing / media pages: their teasers duplicate CMS items, so the RSC-tree text is not indexed.
LISTING_PATHS = {"/", "/news", "/articles", "/events", "/photos", "/podcasts", "/annual-report",
                 "/sustainability-report", "/research/rnd/technical-publication", "/research/rnd/activities",
                 "/opportunities", "/our-services"}


def run() -> None:
    docs = cms_docs()
    site = page_docs()
    docs += [d for d in site if not (d["source"] == "site-tree" and (urlparse(d["url"]).path or "/") in LISTING_PATHS)]
    docs += pdf_docs()
    print(f"[process] extracted {len(docs)} docs: {dict(Counter(d['source'].split(':')[0] for d in docs))}")

    docs, stats, freq_report = clean_documents(docs)
    print(f"[process] cleaning: {stats}")

    chunks: list[dict] = []
    for d in docs:
        doc_id = f"{d['doc_type']}-{sha256(d['url'] + str(d['lang']) + d['source'])[:8]}"
        d["doc_id"] = doc_id
        chunks += chunk_document(d, doc_id)
    write_jsonl(C.DOCS_FILE, ({k: v for k, v in d.items() if k not in ("pages", "text")} for d in docs))
    write_jsonl(C.CHUNKS_FILE, chunks)

    total_tokens = sum(count_tokens(d["full_text"]) for d in docs)
    print(f"[process] {len(docs)} docs, {len(chunks)} chunks, corpus ~{total_tokens:,} tokens")
    print(f"[process] chunks by type: {dict(Counter(c['doc_type'] for c in chunks))}")
    print(f"[process] chunks by lang: {dict(Counter(c['lang'] for c in chunks))}")

    # Manual-review report: most frequent blocks + random chunk samples.
    with open(C.CLEANING_REPORT, "w", encoding="utf-8") as f:
        f.write(f"Cleaning stats: {stats}\nCorpus tokens: {total_tokens}\n\n== Most frequent blocks (removed if over threshold) ==\n")
        for block, c in freq_report[:50]:
            f.write(f"{c:4d}  {block[:160]}\n")
        f.write("\n== 20 random chunks ==\n")
        for c in random.Random(0).sample(chunks, min(20, len(chunks))):
            f.write(f"\n--- {c['chunk_id']} {c['url']} ({c['tokens']} tok)\n{c['text'][:1200]}\n")
    print(f"[process] review report -> {C.CLEANING_REPORT.relative_to(C.ROOT)}")
