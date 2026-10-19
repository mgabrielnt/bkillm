"""Collections from the public Strapi CMS (cms.bki.co.id/api), saved as JSON in data/raw/cms/.

News, articles, events and ESG pages are fetched in both English and Indonesian; the report
collections only list PDF files (downloaded by pdfs.py).
"""
from __future__ import annotations

import json

from ...core import config as C
from ...core.utils import sha256
from .fetcher import Fetcher, now

CMS_COLLECTIONS = [  # (collection, locales, extra query)
    ("newss", ["en", "id"], "populate=*"),
    ("articles", ["en", "id"], "populate=*"),
    ("events", ["en", "id"], "populate=*"),
    ("keberlanjutans", ["en", "id"], "populate=*"),
    ("job-postings", [None], "populate=*"),
    ("annual-reports", [None], "populate[document][populate]=*&sort[0]=date:desc"),
    ("sustainability-reports", [None], "populate[document][populate]=*&sort[0]=date:desc"),
]


def fetch_collection(fetcher: Fetcher, name: str, query: str, locale: str | None) -> list[dict]:
    """All items of one collection, following Strapi pagination."""
    items, page = [], 1
    while True:
        url = f"{C.CMS_API}/{name}?{query}&pagination[pageSize]=100&pagination[page]={page}"
        if locale:
            url += f"&locale={locale}"
        data = fetcher.get(url).json()
        items += data.get("data", [])
        if page >= data.get("meta", {}).get("pagination", {}).get("pageCount", 1):
            return items
        page += 1


def crawl_cms(fetcher: Fetcher, manifest: list[dict]) -> None:
    C.RAW_CMS.mkdir(parents=True, exist_ok=True)
    for name, locales, query in CMS_COLLECTIONS:
        for loc in locales:
            items = fetch_collection(fetcher, name, query, loc)
            fname = f"{name}_{loc or 'all'}.json"
            payload = json.dumps(items, ensure_ascii=False, indent=1)
            (C.RAW_CMS / fname).write_text(payload, encoding="utf-8")
            manifest.append({"url": f"{C.CMS_API}/{name}" + (f"?locale={loc}" if loc else ""), "status": "ok",
                             "source": "cms", "content_type": "application/json", "fetched_at": now(),
                             "sha256": sha256(payload), "raw_path": f"data/raw/cms/{fname}",
                             "items": len(items)})
            print(f"[crawl] cms {name} [{loc or 'all'}]: {len(items)} items")
