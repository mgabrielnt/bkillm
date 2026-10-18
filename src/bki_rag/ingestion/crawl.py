"""Stage 1 - crawling. Stores raw responses untouched plus one manifest row per URL.

bki.co.id is a Next.js app backed by a public Strapi CMS (cms.bki.co.id/api):
  * news, articles, events, ESG pages, job postings and report PDFs come from the CMS JSON API
    (clean structured text, both English and Indonesian locales);
  * static pages (services, company profile, ...) are fetched as HTML. Their text lives in the
    i18n dictionary embedded in the page's React Server Components payload, which `extract.py` parses.
The site sits behind a WAF; we identify honestly, go slowly (1 req/s) and never try to evade it.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from ..core import config as C
from ..core.utils import sha256, write_jsonl

REJECTED_MARKER = b"The requested URL was rejected"
CMS_DETAIL_PREFIXES = ("/news/", "/articles/", "/events/", "/research/rnd/technical-publication/")


class Fetcher:
    """Polite HTTP client: honest UA, fixed delay, retry with backoff on 5xx / WAF rejections."""

    def __init__(self, delay: float = C.REQUEST_DELAY_S):
        self.delay = delay
        self._last = 0.0
        self.client = httpx.Client(headers={"User-Agent": C.USER_AGENT}, timeout=120, follow_redirects=True)

    def get(self, url: str, retries: int = 4) -> httpx.Response:
        for attempt in range(retries + 1):
            wait = self.delay - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            try:
                resp = self.client.get(url)
            except httpx.HTTPError:
                resp = None
            self._last = time.time()
            rejected = resp is not None and REJECTED_MARKER in resp.content[:400]
            if resp is not None and resp.status_code < 500 and not rejected:
                return resp
            if attempt < retries:
                time.sleep(2 ** attempt * 2)
        if resp is None:
            raise RuntimeError(f"network error: {url}")
        return resp


def _slug(url: str) -> str:
    path = urlparse(url).path.strip("/") or "home"
    return re.sub(r"[^a-zA-Z0-9]+", "_", path)[:150]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_sitemap(fetcher: Fetcher) -> list[dict]:
    xml = fetcher.get(C.SITEMAP_URL).text
    rows = []
    for block in re.findall(r"<url>(.*?)</url>", xml, re.S):
        loc = re.search(r"<loc>(.*?)</loc>", block)
        lastmod = re.search(r"<lastmod>(.*?)</lastmod>", block)
        if loc:
            rows.append({"url": loc.group(1).strip().rstrip("/"), "lastmod": lastmod.group(1) if lastmod else None})
    return rows


def crawl_site_pages(fetcher: Fetcher, manifest: list[dict]) -> None:
    """Fetch every sitemap page that is not a CMS detail page (those come cleaner from the API)."""
    C.RAW_SITE.mkdir(parents=True, exist_ok=True)
    pages = [p for p in read_sitemap(fetcher) if not urlparse(p["url"]).path.startswith(CMS_DETAIL_PREFIXES)]
    print(f"[crawl] {len(pages)} site pages")
    for p in pages:
        resp = fetcher.get(p["url"])
        final = str(resp.url)
        rec = {"url": p["url"], "final_url": final, "lastmod": p["lastmod"], "fetched_at": _now(),
               "content_type": resp.headers.get("content-type", ""), "source": "site"}
        if "/login" in urlparse(final).path or resp.status_code in (401, 403):
            rec["status"] = "auth_required"  # never log in, just skip
        elif resp.status_code != 200 or REJECTED_MARKER in resp.content[:400]:
            rec["status"] = f"error_{resp.status_code}"
        else:
            path = C.RAW_SITE / f"{_slug(p['url'])}.html"
            path.write_bytes(resp.content)
            rec.update(status="ok", sha256=sha256(resp.content), raw_path=str(path.relative_to(C.ROOT)))
        manifest.append(rec)
    # Indonesian i18n dictionary for the static pages (English is embedded in every page payload).
    resp = fetcher.get(f"{C.SITE_URL}/locales/id/common.json")
    if resp.status_code == 200 and resp.content.startswith(b"{"):
        path = C.RAW_SITE / "locale_id.json"
        path.write_bytes(resp.content)
        manifest.append({"url": str(resp.url), "status": "ok", "source": "site", "fetched_at": _now(),
                         "content_type": "application/json", "sha256": sha256(resp.content),
                         "raw_path": str(path.relative_to(C.ROOT))})


CMS_COLLECTIONS = [
    # (collection, locales, extra query)
    ("newss", ["en", "id"], "populate=*"),
    ("articles", ["en", "id"], "populate=*"),
    ("events", ["en", "id"], "populate=*"),
    ("keberlanjutans", ["en", "id"], "populate=*"),
    ("job-postings", [None], "populate=*"),
    ("annual-reports", [None], "populate[document][populate]=*&sort[0]=date:desc"),
    ("sustainability-reports", [None], "populate[document][populate]=*&sort[0]=date:desc"),
]


def crawl_cms(fetcher: Fetcher, manifest: list[dict]) -> None:
    C.RAW_CMS.mkdir(parents=True, exist_ok=True)
    for name, locales, query in CMS_COLLECTIONS:
        for loc in locales:
            items, page = [], 1
            while True:
                url = f"{C.CMS_API}/{name}?{query}&pagination[pageSize]=100&pagination[page]={page}"
                if loc:
                    url += f"&locale={loc}"
                data = fetcher.get(url).json()
                items += data.get("data", [])
                pg = data.get("meta", {}).get("pagination", {})
                if page >= pg.get("pageCount", 1):
                    break
                page += 1
            fname = f"{name}_{loc or 'all'}.json"
            payload = json.dumps(items, ensure_ascii=False, indent=1)
            (C.RAW_CMS / fname).write_text(payload, encoding="utf-8")
            manifest.append({"url": f"{C.CMS_API}/{name}" + (f"?locale={loc}" if loc else ""), "status": "ok",
                             "source": "cms", "content_type": "application/json", "fetched_at": _now(),
                             "sha256": sha256(payload), "raw_path": f"data/raw/cms/{fname}", "items": len(items)})
            print(f"[crawl] cms {name} [{loc or 'all'}]: {len(items)} items")


def _report_files(collection: str, limit_years: list[int] | None, limit: int | None) -> list[dict]:
    items = json.loads((C.RAW_CMS / f"{collection}_all.json").read_text(encoding="utf-8"))
    out = []
    for it in items:
        year = int(str(it.get("date") or it.get("title") or "0")[:4] or 0)
        if limit_years is not None and year not in limit_years:
            continue
        docs = it.get("document") or []
        for d in docs if isinstance(docs, list) else [docs]:
            if d and d.get("url", "").lower().endswith(".pdf"):
                out.append({"url": C.CMS_URL + d["url"], "title": it.get("title"), "year": year, "collection": collection})
    return out[:limit] if limit else out


def crawl_pdfs(fetcher: Fetcher, manifest: list[dict]) -> None:
    C.RAW_PDF.mkdir(parents=True, exist_ok=True)
    targets = _report_files("annual-reports", C.ANNUAL_REPORT_YEARS, None)
    targets += _report_files("sustainability-reports", None, C.SUSTAINABILITY_REPORT_LIMIT)
    # PDFs linked directly from static pages (e.g. policy documents).
    seen = {t["url"] for t in targets}
    for html in C.RAW_SITE.glob("*.html"):
        for href in re.findall(r'(?<=["(])(/[\w\-./%]{1,200}\.pdf)', html.read_text(encoding="utf-8", errors="ignore")):
            url = C.SITE_URL + href
            if url not in seen:
                seen.add(url)
                targets.append({"url": url, "title": href.rsplit("/", 1)[-1], "year": None, "collection": "site-pdf"})
    for t in targets:
        path = C.RAW_PDF / f"{sha256(t['url'])[:16]}.pdf"
        rec = {"url": t["url"], "fetched_at": _now(), "source": "pdf", "content_type": "application/pdf",
               "title": t["title"], "year": t["year"], "collection": t["collection"], "status": "ok"}
        if not path.exists():  # PDFs are large and immutable per URL: download once
            resp = fetcher.get(t["url"])
            if resp.status_code == 200 and resp.content[:4] == b"%PDF":
                path.write_bytes(resp.content)
            else:
                rec["status"] = f"error_{resp.status_code}"
        if path.exists():
            content = path.read_bytes()
            rec.update(sha256=sha256(content), raw_path=str(path.relative_to(C.ROOT)), size_mb=round(len(content) / 1e6, 1))
        manifest.append(rec)
        print(f"[crawl] pdf {t['title']}: {rec['status']} {rec.get('size_mb', '')}MB")


def run() -> None:
    fetcher = Fetcher()
    manifest: list[dict] = []
    crawl_cms(fetcher, manifest)
    crawl_site_pages(fetcher, manifest)
    crawl_pdfs(fetcher, manifest)
    write_jsonl(C.MANIFEST, manifest)
    by_status: dict[str, int] = {}
    for m in manifest:
        by_status[m["status"]] = by_status.get(m["status"], 0) + 1
    print(f"[crawl] manifest: {len(manifest)} rows {by_status}")
