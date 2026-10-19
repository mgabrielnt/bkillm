"""Stage 3 - layered cleaning and de-duplication.

1. Line heuristics (bilingual "read more"/"share"/copyright lines, bare page numbers).
2. Cross-document frequency: blocks repeated across many documents of the same source are
   template text (menus, footers, office addresses) and are dropped. For PDFs the same idea runs
   per document across pages to remove running headers/footers.
3. Normalisation (NFKC, control chars, hyphenation, whitespace).
4. Exact dedup (sha256 of normalised text) and near-dup dedup (MinHash LSH, 5-word shingles, J>=0.8).
5. Quality gate: documents with < 50 words are dropped.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from datasketch import MinHash, MinHashLSH

from ..core.utils import normalize_text, sha256

BOILERPLATE_LINE = re.compile(
    r"^\W*(read more|baca selengkapnya|selengkapnya|share( this)?|bagikan|back|kembali|next|previous|sebelumnya|"
    r"berikutnya|load more|lihat semua|view all|see all|download|unduh|click here|klik di sini|"
    r"(©|copyright|hak cipta).*|all rights reserved.*|\d+\s*(views?|dilihat)|page \d+( of \d+)?|halaman \d+|\d{1,4})\W*$",
    re.I,
)


def _norm_block(b: str) -> str:
    return re.sub(r"\d", "0", re.sub(r"\s+", " ", b.lower())).strip()


def _blocks(text: str) -> list[str]:
    return [b for b in re.split(r"\n\s*\n|\n(?=[-*#|] )", text) if b.strip()]


def line_filter(text: str) -> str:
    keep = [l for l in text.split("\n") if not BOILERPLATE_LINE.match(l.strip())]
    return "\n".join(keep)


def frequency_filter(docs: list[dict], key: str, ratio: float = 0.2, min_docs: int = 5,
                     short_words: int = 15) -> tuple[list[dict], list[tuple[str, int]]]:
    """Drop blocks that appear in > ratio of docs (or >= min_docs and short) within each `key` group."""
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
            df.update({_norm_block(b) for b in _blocks(d["text"])[1:]})  # first block = title, never counted
        bad = {b for b, c in df.items()
               if (c / n > ratio or (c >= min_docs and len(b.split()) < short_words)) and c >= 3}
        report += [(b, c) for b, c in df.most_common(60)]
        for d in group_docs:
            blocks = _blocks(d["text"])
            d["text"] = "\n\n".join(blocks[:1] + [b for b in blocks[1:] if _norm_block(b) not in bad])
    report.sort(key=lambda x: -x[1])
    return docs, report


def pdf_header_footer_filter(pages: list[dict], ratio: float = 0.3) -> list[dict]:
    """Remove lines that repeat on many pages of one PDF (running headers/footers)."""
    n = len(pages)
    df = Counter()
    for p in pages:
        df.update({_norm_block(l) for l in p["text"].split("\n") if l.strip()})
    bad = {l for l, c in df.items() if c >= max(3, ratio * n) and len(l.split()) < 15}
    out = []
    for p in pages:
        lines = [l for l in p["text"].split("\n") if _norm_block(l) not in bad]
        out.append({**p, "text": line_filter("\n".join(lines))})
    return out


def _minhash(text: str) -> MinHash:
    words = re.findall(r"\w+", text.lower())
    m = MinHash(num_perm=128)
    for i in range(max(1, len(words) - 4)):
        m.update(" ".join(words[i:i + 5]).encode("utf-8"))
    return m


def dedup(docs: list[dict]) -> tuple[list[dict], int, int]:
    """Exact then near-duplicate removal. Duplicates become `aliases` of the kept document."""
    by_hash: dict[str, dict] = {}
    exact = 0
    for d in docs:
        h = sha256(_norm_block(d["full_text"]))
        if h in by_hash:
            keep = by_hash[h]
            if d["url"] != keep["url"]:
                keep.setdefault("aliases", []).append(d["url"])
            exact += 1
            continue
        by_hash[h] = d
    uniq = list(by_hash.values())
    lsh = MinHashLSH(threshold=0.8, num_perm=128)
    kept: list[dict] = []
    near = 0
    for i, d in enumerate(sorted(uniq, key=lambda x: -len(x["full_text"]))):
        mh = _minhash(d["full_text"])
        hits = lsh.query(mh)
        if hits:
            keep = kept[hits[0]]
            if d["url"] != keep["url"]:
                keep.setdefault("aliases", []).append(d["url"])
            near += 1
            continue
        lsh.insert(len(kept), mh)
        kept.append(d)
    return kept, exact, near


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
        d["pages"] = [{**p, "text": normalize_text(p["text"])} for p in d["pages"]]
        d["pages"] = pdf_header_footer_filter(d["pages"])
        d["full_text"] = "\n\n".join(p["text"] for p in d["pages"])
    docs = md_docs + pdf_docs
    docs, stats["exact_dups"], stats["near_dups"] = dedup(docs)
    before = len(docs)
    docs = [d for d in docs if len(d["full_text"].split()) >= 50]
    stats["too_short"] = before - len(docs)
    stats["output"] = len(docs)
    return docs, stats, report
