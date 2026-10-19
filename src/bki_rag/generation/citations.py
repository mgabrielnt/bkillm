"""Citations in the model's answer -> a clean, matching source list.

The model cites the 10 sources it was given by their position ([4], [9], ...). For the reader those numbers
are renumbered 1, 2, 3... in order of first appearance, several chunks of the same page share one number,
and the source list uses exactly the same numbers.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

_CITATION = re.compile(r"\[((?:(?:sources?|sumber)\s*)?\d+(?:\s*[,;]\s*(?:(?:sources?|sumber)\s*)?\d+)*)\]", re.I)
_RUN = re.compile(r"(?:\[\d+\])+")


def normalize_citations(text: str) -> str:
    """Small models sometimes write [source 5; source 3] or [1, 2]; rewrite those as [5][3] / [1][2]."""
    return _CITATION.sub(lambda m: "".join(f"[{n}]" for n in re.findall(r"\d+", m.group(1))), text)


def display_title(chunk: dict) -> str:
    """Readable title; generic page titles ("BKI | Biro Klasifikasi ...") are named after the URL path."""
    title = chunk["title"].strip()
    if title.startswith("BKI |") or title in ("BKI", "Biro Klasifikasi Indonesia"):
        last = urlparse(chunk["url"]).path.strip("/").split("/")[-1]
        return last.replace("-", " ").title() if last else "Beranda BKI"
    return title


def _source_key(chunk: dict) -> tuple:
    pages = (chunk["page_from"], chunk["page_to"]) if chunk.get("page_from") else None
    return chunk["url"], pages


def renumber_citations(text: str, chunks: list[dict]) -> tuple[str, list[dict]]:
    """Returns (answer with citations renumbered 1..k, sources [{"n", "title", "url", "pages"}])."""
    text = normalize_citations(text)
    mapping: dict[int, int] = {}
    numbers: dict[tuple, int] = {}
    sources: list[dict] = []
    for m in re.finditer(r"\[(\d+)\]", text):
        n = int(m.group(1))
        if n in mapping or not 0 < n <= len(chunks):
            continue
        key = _source_key(chunks[n - 1])
        if key not in numbers:
            numbers[key] = len(sources) + 1
            sources.append({"n": numbers[key], "title": display_title(chunks[n - 1]), "url": key[0],
                            "pages": key[1]})
        mapping[n] = numbers[key]

    def rewrite_run(m: re.Match) -> str:
        new = [mapping.get(int(n), int(n)) for n in re.findall(r"\d+", m.group(0))]
        return "".join(f"[{n}]" for n in dict.fromkeys(new))  # [2][4] -> [2] when both are the same page

    return _RUN.sub(rewrite_run, text), sources
