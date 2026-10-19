"""Building blocks for chunking: paragraph units with heading paths, splitting of oversized units,
and language detection for documents without a known language (PDFs)."""
from __future__ import annotations

import re

from langdetect import DetectorFactory, detect

from ...core.utils import count_tokens

DetectorFactory.seed = 0  # deterministic language detection
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def detect_lang(text: str) -> str:
    try:
        return "id" if detect(text[:2000]) == "id" else "en"
    except Exception:
        return "en"


def units(doc: dict) -> list[dict]:
    """Flatten a doc into paragraph units {"text", "path" (heading titles), "page"}."""
    pages = doc.get("pages") or [{"page": None, "text": doc["text"]}]
    path: list[tuple[int, str]] = []
    out: list[dict] = []
    for p in pages:
        for block in re.split(r"\n\s*\n", p["text"]):
            block = block.strip()
            if not block:
                continue
            m = HEADING.match(block.split("\n", 1)[0])
            if m:
                level, title = len(m.group(1)), re.sub(r"[*_`]", "", m.group(2)).strip()
                path = [(lvl, t) for lvl, t in path if lvl < level] + [(level, title)]
                block = block.split("\n", 1)[1].strip() if "\n" in block else ""
                if not block:
                    continue
            out.append({"text": block, "path": [t for _, t in path], "page": p["page"]})
    return out


def split_long(text: str, max_tokens: int) -> list[str]:
    """Split an oversized unit: tables by rows (header repeated), prose by sentences."""
    if count_tokens(text) <= max_tokens:
        return [text]
    lines = text.split("\n")
    if lines[0].startswith("|") and len(lines) > 3:
        header, parts, cur = lines[:2], [], []
        for row in lines[2:]:
            if cur and count_tokens("\n".join(header + cur + [row])) > max_tokens:
                parts.append("\n".join(header + cur))
                cur = []
            cur.append(row)
        return parts + (["\n".join(header + cur)] if cur else [])
    parts, cur = [], ""
    for s in re.split(r"(?<=[.!?;])\s+|\n", text):
        if cur and count_tokens(cur + " " + s) > max_tokens:
            parts.append(cur)
            cur = ""
        cur = (cur + " " + s).strip()
    return parts + ([cur] if cur else [])
