"""Documents from the downloaded PDFs, one Markdown section per page so chunks can cite page numbers.

Parsing with pymupdf4llm is the slow step (minutes per report), so each PDF's result is cached in
data/cache/pdf_<hash>.json and reused on later runs.
"""
from __future__ import annotations

import json
from pathlib import Path

from ...core import config as C
from ...core.utils import read_jsonl

_KINDS = {"annual-reports": "annual_report", "sustainability-reports": "sustainability_report"}


# Markdown per halaman sebuah PDF (dari cache, atau diurai lalu disimpan ke cache).
def _pages(m: dict) -> list[dict]:
    cache = C.CACHE_DIR / f"pdf_{m['sha256'][:16]}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    import pymupdf4llm  # hanya perlu saat membangun (ulang) data

    print(f"[extract] pdf {m['title']} ({m.get('size_mb')} MB) ...", flush=True)
    pages = pymupdf4llm.to_markdown(str(C.ROOT / m["raw_path"]), page_chunks=True, show_progress=False,
                                    ignore_images=True, ignore_graphics=True)
    pages = [{"metadata": {"page": (p.get("metadata") or {}).get("page")}, "text": p["text"]} for p in pages]
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
    return pages


# Satu dokumen per PDF yang diunduh, nomor halaman tetap disimpan.
def pdf_docs() -> list[dict]:
    docs = []
    for m in read_jsonl(C.MANIFEST):
        if m["source"] != "pdf" or m["status"] != "ok":
            continue
        kind = _KINDS.get(m["collection"], "policy")
        title = {"annual_report": f"BKI Annual Report {m['year']}", "sustainability_report": f"BKI {m['title']}"}
        docs.append({
            "url": m["url"], "lang": None, "doc_type": kind, "source": "pdf", "lastmod": None,
            "title": title.get(kind, Path(m["title"]).stem.replace("-", " ").replace("_", " ")),
            "published_at": f"{m['year']}-12-31" if m.get("year") else None,
            "pages": [{"page": (p.get("metadata") or {}).get("page") or i + 1, "text": p["text"]}
                      for i, p in enumerate(_pages(m))],
        })
    return docs
