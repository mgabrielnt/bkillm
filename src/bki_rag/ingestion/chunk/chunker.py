"""Pack paragraph units into chunks of ~CHUNK_TARGET_TOKENS and attach citation metadata.

Rules: a short web document (<= CHUNK_MAX_TOKENS) stays one chunk; a new chunk starts at a new section
once the current one is half full; when a cut falls inside a section, its last short paragraph is
repeated at the start of the next chunk (~10% overlap). Each chunk text starts with a breadcrumb
"Title > Section > Subsection".
"""
from __future__ import annotations

from ...core import config as C
from ...core.utils import count_tokens, sha256
from .units import detect_lang, split_long, units


def _pack(doc: dict) -> list[list[dict]]:
    """Group a document's paragraph units into chunk-sized lists."""
    target, max_tok = C.CHUNK_TARGET_TOKENS, C.CHUNK_MAX_TOKENS
    us = units(doc)
    if "pages" not in doc and count_tokens(doc["full_text"]) <= max_tok:
        return [us]
    groups: list[list[dict]] = []
    cur: list[dict] = []
    cur_tok = 0
    for u in us:
        for piece in split_long(u["text"], max_tok):
            pu = {**u, "text": piece}
            tok = count_tokens(piece)
            new_section = cur and u["path"][:2] != cur[-1]["path"][:2] and cur_tok > target * 0.5
            if cur and (cur_tok + tok > target or new_section):
                groups.append(cur)
                last = cur[-1]
                overlap = (not new_section and last["path"] == pu["path"]
                           and count_tokens(last["text"]) < target * 0.15)
                cur = [last] if overlap else []
                cur_tok = sum(count_tokens(x["text"]) for x in cur)
            cur.append(pu)
            cur_tok += tok
    return groups + ([cur] if cur else [])


def chunk_document(doc: dict, doc_id: str) -> list[dict]:
    """Turn one clean document into chunk records with breadcrumb and citation metadata."""
    chunks = []
    for i, g in enumerate(x for x in _pack(doc) if x):
        section = next((u["path"] for u in reversed(g) if u["path"]), [])
        section = [s for s in section if s.strip() and s.strip() != doc["title"]]
        body = "\n\n".join(u["text"] for u in g)
        pages = [u["page"] for u in g if u["page"] is not None]
        text = " > ".join([doc["title"]] + section[-2:]) + f"\n\n{body}"
        chunks.append({
            "chunk_id": f"{doc_id}-{i:03d}", "doc_id": doc_id, "chunk_index": i,
            "url": doc["url"], "aliases": doc.get("aliases", []), "group_id": doc.get("group_id") or doc["url"],
            "title": doc["title"], "section_path": " > ".join(section), "doc_type": doc["doc_type"],
            "lang": doc["lang"] or detect_lang(body), "published_at": doc.get("published_at"),
            "page_from": min(pages) if pages else None, "page_to": max(pages) if pages else None,
            "text": text, "tokens": count_tokens(text), "content_hash": sha256(text),
        })
    return chunks
