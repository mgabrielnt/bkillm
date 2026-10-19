"""Static website pages from the sitemap, plus the Indonesian i18n dictionary.

CMS detail pages (news, articles, events) are skipped here because cms.py fetches them cleaner from the
API. Pages that redirect to /login are recorded as auth_required and never logged into.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from ...core import config as C
from ...core.utils import sha256
from .fetcher import Fetcher, is_rejected, now, slug

CMS_DETAIL_PREFIXES = ("/news/", "/articles/", "/events/", "/research/rnd/technical-publication/")


def read_sitemap(fetcher: Fetcher) -> list[dict]:
    xml = fetcher.get(C.SITEMAP_URL).text
    rows = []
    for block in re.findall(r"<url>(.*?)</url>", xml, re.S):
        loc = re.search(r"<loc>(.*?)</loc>", block)
        lastmod = re.search(r"<lastmod>(.*?)</lastmod>", block)
        if loc:
            rows.append({"url": loc.group(1).strip().rstrip("/"),
                         "lastmod": lastmod.group(1) if lastmod else None})
    return rows


def crawl_site_pages(fetcher: Fetcher, manifest: list[dict]) -> None:
    """Save every non-CMS sitemap page as raw HTML (data/raw/site/) with a manifest row."""
    C.RAW_SITE.mkdir(parents=True, exist_ok=True)
    pages = [p for p in read_sitemap(fetcher) if not urlparse(p["url"]).path.startswith(CMS_DETAIL_PREFIXES)]
    print(f"[crawl] {len(pages)} site pages")
    for p in pages:
        resp = fetcher.get(p["url"])
        final = str(resp.url)
        rec = {"url": p["url"], "final_url": final, "lastmod": p["lastmod"], "fetched_at": now(),
               "content_type": resp.headers.get("content-type", ""), "source": "site"}
        if "/login" in urlparse(final).path or resp.status_code in (401, 403):
            rec["status"] = "auth_required"
        elif resp.status_code != 200 or is_rejected(resp.content):
            rec["status"] = f"error_{resp.status_code}"
        else:
            path = C.RAW_SITE / f"{slug(p['url'])}.html"
            path.write_bytes(resp.content)
            rec.update(status="ok", sha256=sha256(resp.content), raw_path=str(path.relative_to(C.ROOT)))
        manifest.append(rec)
    _crawl_id_dictionary(fetcher, manifest)


def _crawl_id_dictionary(fetcher: Fetcher, manifest: list[dict]) -> None:
    """Indonesian texts of the static pages (the English ones are embedded in every page payload)."""
    resp = fetcher.get(f"{C.SITE_URL}/locales/id/common.json")
    if resp.status_code == 200 and resp.content.startswith(b"{"):
        path = C.RAW_SITE / "locale_id.json"
        path.write_bytes(resp.content)
        manifest.append({"url": str(resp.url), "status": "ok", "source": "site", "fetched_at": now(),
                         "content_type": "application/json", "sha256": sha256(resp.content),
                         "raw_path": str(path.relative_to(C.ROOT))})
