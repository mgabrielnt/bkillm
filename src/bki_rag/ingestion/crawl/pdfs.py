"""Report PDFs (annual + sustainability reports from the CMS) and PDFs linked from static pages.

Which reports are downloaded is set by ANNUAL_REPORT_YEARS and SUSTAINABILITY_REPORT_LIMIT. Files are
named by URL hash and downloaded only once, because they are large and never change per URL.
"""
from __future__ import annotations

import json
import re

from ...core import config as C
from ...core.utils import sha256
from .fetcher import Fetcher, now

_PDF_LINK = re.compile(r'(?<=["(])(/[\w\-./%]{1,200}\.pdf)')


def report_files(collection: str, years: list[int] | None, limit: int | None) -> list[dict]:
    """PDF targets listed in a CMS report collection (crawl the CMS first)."""
    items = json.loads((C.RAW_CMS / f"{collection}_all.json").read_text(encoding="utf-8"))
    out = []
    for it in items:
        year = int(str(it.get("date") or it.get("title") or "0")[:4] or 0)
        if years is not None and year not in years:
            continue
        docs = it.get("document") or []
        for d in docs if isinstance(docs, list) else [docs]:
            if d and d.get("url", "").lower().endswith(".pdf"):
                out.append({"url": C.CMS_URL + d["url"], "title": it.get("title"), "year": year,
                            "collection": collection})
    return out[:limit] if limit else out


def linked_pdfs(known: set[str]) -> list[dict]:
    """PDFs linked from the saved static pages (e.g. policy documents)."""
    out = []
    for html in C.RAW_SITE.glob("*.html"):
        for href in _PDF_LINK.findall(html.read_text(encoding="utf-8", errors="ignore")):
            url = C.SITE_URL + href
            if url not in known:
                known.add(url)
                out.append({"url": url, "title": href.rsplit("/", 1)[-1], "year": None, "collection": "site-pdf"})
    return out


def crawl_pdfs(fetcher: Fetcher, manifest: list[dict]) -> None:
    C.RAW_PDF.mkdir(parents=True, exist_ok=True)
    targets = report_files("annual-reports", C.ANNUAL_REPORT_YEARS, None)
    targets += report_files("sustainability-reports", None, C.SUSTAINABILITY_REPORT_LIMIT)
    targets += linked_pdfs({t["url"] for t in targets})
    for t in targets:
        path = C.RAW_PDF / f"{sha256(t['url'])[:16]}.pdf"
        rec = {"url": t["url"], "fetched_at": now(), "source": "pdf", "content_type": "application/pdf",
               "title": t["title"], "year": t["year"], "collection": t["collection"], "status": "ok"}
        if not path.exists():
            resp = fetcher.get(t["url"])
            if resp.status_code == 200 and resp.content[:4] == b"%PDF":
                path.write_bytes(resp.content)
            else:
                rec["status"] = f"error_{resp.status_code}"
        if path.exists():
            content = path.read_bytes()
            rec.update(sha256=sha256(content), raw_path=str(path.relative_to(C.ROOT)),
                       size_mb=round(len(content) / 1e6, 1))
        manifest.append(rec)
        print(f"[crawl] pdf {t['title']}: {rec['status']} {rec.get('size_mb', '')}MB")
