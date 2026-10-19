"""Stage 1 - crawling: store raw responses untouched plus one manifest row per URL.

Modules:
  fetcher.py  polite HTTP client (honest User-Agent, 1 request/s, backoff) and helpers
  cms.py      CMS API collections: news, articles, events, ESG pages, jobs, report lists
  site.py     static sitemap pages (HTML) and the Indonesian i18n dictionary
  pdfs.py     annual / sustainability report PDFs and PDFs linked from pages
"""
from __future__ import annotations

from collections import Counter

from ...core import config as C
from ...core.utils import write_jsonl
from .cms import crawl_cms
from .fetcher import Fetcher
from .pdfs import crawl_pdfs
from .site import crawl_site_pages


def run() -> None:
    """Crawl everything into data/raw/ and write data/raw/manifest.jsonl."""
    fetcher = Fetcher()
    manifest: list[dict] = []
    crawl_cms(fetcher, manifest)
    crawl_site_pages(fetcher, manifest)
    crawl_pdfs(fetcher, manifest)  # needs the CMS report lists and saved pages from the steps above
    write_jsonl(C.MANIFEST, manifest)
    print(f"[crawl] manifest: {len(manifest)} rows {dict(Counter(m['status'] for m in manifest))}")
