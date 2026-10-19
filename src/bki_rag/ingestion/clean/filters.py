"""Boilerplate removal: bilingual line heuristics and frequency filters.

Template text (menus, footers, office addresses, PDF running headers) is found by how often a block
repeats across documents, not by looking at a single page.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

BOILERPLATE_LINE = re.compile(
    r"^\W*(read more|baca selengkapnya|selengkapnya|share( this)?|bagikan|back|kembali|next|previous|sebelumnya|"
    r"berikutnya|load more|lihat semua|view all|see all|download|unduh|click here|klik di sini|"
    r"(©|copyright|hak cipta).*|all rights reserved.*|\d+\s*(views?|dilihat)|page \d+( of \d+)?|halaman \d+"
    r"|\d{1,4})\W*$",
    re.I,
)


def norm_block(b: str) -> str:
    """Comparison key: lowercase, single spaces, digits replaced by 0."""
    return re.sub(r"\d", "0", re.sub(r"\s+", " ", b.lower())).strip()


def blocks(text: str) -> list[str]:
    return [b for b in re.split(r"\n\s*\n|\n(?=[-*#|] )", text) if b.strip()]


def line_filter(text: str) -> str:
    """Drop lines such as "Read more", "Bagikan", copyright notices and bare page numbers."""
    return "\n".join(line for line in text.split("\n") if not BOILERPLATE_LINE.match(line.strip()))


def frequency_filter(docs: list[dict], key: str, ratio: float = 0.2, min_docs: int = 5,
                     short_words: int = 15) -> tuple[list[dict], list[tuple[str, int]]]:
    """Drop blocks found in > ratio of the docs (or in >= min_docs docs and short) within each `key` group.

    Returns the docs and the most frequent blocks, for the manual-review report.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for d in docs:
        groups[d[key]].append(d)
    report: list[tuple[str, int]] = []
    for group_docs in groups.values():
        n = len(group_docs)
        if n < min_docs:
            continue
        df = Counter()
        for d in group_docs:
            df.update({norm_block(b) for b in blocks(d["text"])[1:]})  # first block = title, never counted
        bad = {b for b, c in df.items()
               if (c / n > ratio or (c >= min_docs and len(b.split()) < short_words)) and c >= 3}
        report += df.most_common(60)
        for d in group_docs:
            bl = blocks(d["text"])
            d["text"] = "\n\n".join(bl[:1] + [b for b in bl[1:] if norm_block(b) not in bad])
    report.sort(key=lambda x: -x[1])
    return docs, report


def pdf_header_footer_filter(pages: list[dict], ratio: float = 0.3) -> list[dict]:
    """Remove short lines that repeat on many pages of one PDF (running headers/footers)."""
    df = Counter()
    for p in pages:
        df.update({norm_block(line) for line in p["text"].split("\n") if line.strip()})
    bad = {line for line, c in df.items() if c >= max(3, ratio * len(pages)) and len(line.split()) < 15}
    out = []
    for p in pages:
        lines = [line for line in p["text"].split("\n") if norm_block(line) not in bad]
        out.append({**p, "text": line_filter("\n".join(lines))})
    return out
