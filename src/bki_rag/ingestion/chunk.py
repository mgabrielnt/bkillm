"""Stage 4 - structure-aware chunking with breadcrumbs.

Documents are split on Markdown headings, paragraphs are packed up to ~CHUNK_TARGET_TOKENS,
tables are never split mid-row, short docs (<= CHUNK_MAX_TOKENS) stay a single chunk, and every
chunk starts with a breadcrumb "Title > Section > Subsection" (a free form of contextual retrieval
that also helps BM25). PDF chunks keep page_from/page_to for citations.
"""
from __future__ import annotations

import re

from langdetect import DetectorFactory, detect

from ..core import config as C
from ..core.utils import count_tokens, sha256

DetectorFactory.seed = 0
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def _lang(text: str) -> str:
    try:
        return "id" if detect(text[:2000]) == "id" else "en"
    except Exception:
        return "en"


def _units(doc: dict) -> list[dict]:
    """Flatten a doc into paragraph units carrying their heading path and page number."""
    pages = doc.get("pages") or [{"page": None, "text": doc["text"]}]
    path: list[tuple[int, str]] = []
    units: list[dict] = []
    for p in pages:
        for block in re.split(r"\n\s*\n", p["text"]):
            block = block.strip()
            if not block:
                continue
            m = HEADING.match(block.split("\n", 1)[0])
            if m:
                level, title = len(m.group(1)), re.sub(r"[*_`]", "", m.group(2)).strip()
                path = [(l, t) for l, t in path if l < level] + [(level, title)]
                rest = block.split("\n", 1)[1].strip() if "\n" in block else ""
                if not rest:
                    continue
                block = rest
            units.append({"text": block, "path": [t for _, t in path], "page": p["page"]})
    return units


def _split_long(text: str, max_tokens: int) -> list[str]:
    """Split an oversized paragraph/table: tables by rows (header repeated), prose by sentences."""
    if count_tokens(text) <= max_tokens:
        return [text]
    lines = text.split("\n")
    if lines[0].startswith("|") and len(lines) > 3:
        header, rows = lines[:2], lines[2:]
        parts, cur = [], []
        for r in rows:
            if cur and count_tokens("\n".join(header + cur + [r])) > max_tokens:
                parts.append("\n".join(header + cur))
                cur = []
            cur.append(r)
        return parts + (["\n".join(header + cur)] if cur else [])
    sentences = re.split(r"(?<=[.!?;])\s+|\n", text)
    parts, cur = [], ""
    for s in sentences:
        if cur and count_tokens(cur + " " + s) > max_tokens:
            parts.append(cur)
            cur = ""
        cur = (cur + " " + s).strip()
    return parts + ([cur] if cur else [])


def chunk_document(doc: dict, doc_id: str) -> list[dict]:
    target, max_tok = C.CHUNK_TARGET_TOKENS, C.CHUNK_MAX_TOKENS
    units = _units(doc)
    groups: list[list[dict]] = []
    if "pages" not in doc and count_tokens(doc["full_text"]) <= max_tok:
        groups = [units]  # short page/news item: one chunk
    else:
        cur: list[dict] = []
        cur_tok = 0
        for u in units:
            for piece in _split_long(u["text"], max_tok):
                pu = {**u, "text": piece}
                tok = count_tokens(piece)
                new_section = cur and u["path"][:2] != cur[-1]["path"][:2] and cur_tok > target * 0.5
                if cur and (cur_tok + tok > target or new_section):
                    groups.append(cur)
                    # ~10% overlap when cutting inside a section: carry the last short paragraph over
                    last = cur[-1]
                    carry = [last] if not new_section and last["path"] == pu["path"] and count_tokens(last["text"]) < target * 0.15 else []
                    cur, cur_tok = carry, sum(count_tokens(x["text"]) for x in carry)
                cur.append(pu)
                cur_tok += tok
        if cur:
            groups.append(cur)
    chunks = []
    for i, g in enumerate(x for x in groups if x):
        section = next((u["path"] for u in reversed(g) if u["path"]), [])
        section = [s for s in section if s.strip() and s.strip() != doc["title"]]
        crumb = " > ".join([doc["title"]] + section[-2:])
        body = "\n\n".join(u["text"] for u in g)
        pages = [u["page"] for u in g if u["page"] is not None]
        text = f"{crumb}\n\n{body}"
        chunks.append({
            "chunk_id": f"{doc_id}-{i:03d}", "doc_id": doc_id, "chunk_index": i,
            "url": doc["url"], "aliases": doc.get("aliases", []), "group_id": doc.get("group_id") or doc["url"],
            "title": doc["title"],
            "section_path": " > ".join(section), "doc_type": doc["doc_type"],
            "lang": doc["lang"] or _lang(body), "published_at": doc.get("published_at"),
            "page_from": min(pages) if pages else None, "page_to": max(pages) if pages else None,
            "text": text, "tokens": count_tokens(text), "content_hash": sha256(text),
        })
    return chunks
