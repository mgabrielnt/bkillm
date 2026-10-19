"""Documents from the CMS JSON files: news, articles, events, ESG pages and job postings.

group_id is the CMS documentId, shared by the English and Indonesian version of the same item, so
evaluation can treat a translation as the same source.
"""
from __future__ import annotations

import json
import re

from ...core import config as C
from .tiptap import blocks_md, tiptap_to_md

ESG_URLS = {"environment": "/esgrc/environment", "social": "/esgrc/corporate-social-responsibility",
            "governance": "/esgrc/good-corporate-governance"}
_ANNOUNCEMENT = re.compile(r"pengumuman|announcement|seleksi|selection|rekrutmen|recruitment|tender", re.I)


def _load(name: str) -> list[dict]:
    """Items of one saved CMS collection file ([] if missing)."""
    p = C.RAW_CMS / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def _doc(it: dict, url: str, title: str, lang: str, doc_type: str, source: str, text: str) -> dict:
    """Common document record for a CMS item."""
    return {"url": url, "title": title, "lang": lang, "doc_type": doc_type, "source": source,
            "group_id": it.get("documentId"), "published_at": it.get("publishedAt"),
            "lastmod": it.get("updatedAt"), "text": text}


def _news(it: dict, lang: str) -> dict:
    """Document for a news item or announcement."""
    title = it["title"].strip()
    kind = "announcement" if _ANNOUNCEMENT.search(title) else "news"
    text = f"# {title}\n\n{(it.get('description') or '').strip()}\n\n{blocks_md(it.get('blocks'))}"
    return _doc(it, f"{C.SITE_URL}/news/{it['slug']}", title, lang, kind, "cms:news", text)


def _article(it: dict, lang: str) -> dict:
    """Document for a technical article."""
    title = it["title"].strip()
    author = (it.get("author") or {}).get("name") if isinstance(it.get("author"), dict) else None
    text = (f"# {title}\n\n" + (f"Author: {author}\n\n" if author else "")
            + f"{(it.get('description') or '').strip()}\n\n{blocks_md(it.get('blocks'))}")
    return _doc(it, f"{C.SITE_URL}/articles/{it['slug']}", title, lang, "article", "cms:article", text)


def _event(it: dict, lang: str) -> dict:
    """Document for an event."""
    title = it["title"].strip()
    meta = f"Location: {it.get('location') or '-'}; Date: {it.get('startDate') or '-'}"
    text = f"# {title}\n\n{meta}\n\n{(it.get('description') or '').strip()}\n\n{blocks_md(it.get('blocks'))}"
    return _doc(it, f"{C.SITE_URL}/events/{it['slug']}", title, lang, "event", "cms:event", text)


def _esg(it: dict, lang: str) -> dict:
    """Document for an ESG / sustainability page (TipTap content)."""
    menu = it.get("menu_keberlanjutan") or {}
    section = (menu.get("name") or "").split("-")[0].split("=")[0]
    label = menu.get("label_en" if lang == "en" else "label_id") or ""
    body = tiptap_to_md(it.get("content_tiptap")) or (it.get("content") or "")
    title = it["title"].strip()
    heading = f"# ESG > {section.title() or 'Sustainability'}" + (f" > {label}" if label else "") + f": {title}"
    url = C.SITE_URL + ESG_URLS.get(section, "/esgrc/corporate-social-responsibility")
    return _doc(it, url, title, lang, "esg", "cms:esg", f"{heading}\n\n{body}")


def _job(it: dict) -> dict:
    """Document for a job posting (Indonesian only)."""
    title = it["title"].strip()
    text = f"# Lowongan: {title}\n\nLokasi: {it.get('location') or '-'}\n\n{blocks_md(it.get('blocks'))}"
    doc = _doc(it, f"{C.SITE_URL}/opportunities", title, "id", "job", "cms:job", text)
    doc.pop("group_id")  # job postings have no translations
    return doc


def cms_docs() -> list[dict]:
    """All CMS documents in English and Indonesian."""
    docs = []
    for lang in ("en", "id"):
        docs += [_news(it, lang) for it in _load(f"newss_{lang}.json")]
        docs += [_article(it, lang) for it in _load(f"articles_{lang}.json")]
        docs += [_event(it, lang) for it in _load(f"events_{lang}.json")]
        docs += [_esg(it, lang) for it in _load(f"keberlanjutans_{lang}.json")]
    docs += [_job(it) for it in _load("job-postings_all.json")]
    return docs
