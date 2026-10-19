"""Documents from the static website pages.

Two kinds per page set:
  * "i18n:<namespace>"  one document per dictionary namespace (English from the page payload, Indonesian
                        from locale_id.json); large namespaces are split into their sub-pages.
  * "site-tree"         visible text of each page's element tree (mostly removed later as boilerplate).
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from ...core import config as C
from ...core.utils import read_jsonl
from .i18n import render_namespace
from .rsc import find_translations, merge_resolved, parse_flight, resolve_refs
from .rsc_text import tree_text
from .urls import doc_type_from_url, map_namespace_url

SKIP_NAMESPACES = {"nav", "common", "footer", "header", "auth", "login", "form", "errors", "notFound", "cookie",
                   "search", "pagination", "breadcrumb", "chatbot", "certificate_verification"}


def page_docs() -> list[dict]:
    """Documents for all static pages: dictionary namespaces (EN + ID) and page text."""
    site = [m for m in read_jsonl(C.MANIFEST)
            if m["source"] == "site" and m["status"] == "ok" and m["raw_path"].endswith(".html")]
    site_paths = [urlparse(m["url"]).path or "/" for m in site]
    docs: list[dict] = []
    en_dict = None
    for m in site:
        html = (C.ROOT / m["raw_path"]).read_text(encoding="utf-8", errors="replace")
        rows = parse_flight(html)
        # Long strings (e.g. director bios) are "$ref"s to text rows of the page that renders them, so
        # resolve every page's copy of the dictionary and keep the first resolved value of each key.
        en_dict = merge_resolved(en_dict, resolve_refs(find_translations(rows), rows))
        title = re.search(r"<title>(.*?)</title>", html)
        docs.append({"url": m["url"], "title": (title.group(1) if title else m["url"]).replace(" | BKI", "").strip(),
                     "lang": "en", "doc_type": doc_type_from_url(m["url"]), "source": "site-tree",
                     "published_at": None, "lastmod": m.get("lastmod"), "text": "\n\n".join(tree_text(rows))})
    dicts = {"en": en_dict or {}}
    id_path = C.RAW_SITE / "locale_id.json"
    if id_path.exists():
        dicts["id"] = json.loads(id_path.read_text(encoding="utf-8"))  # the file is the "common" namespace
    for lang, d in dicts.items():
        for ns, val in d.items():
            if ns not in SKIP_NAMESPACES and isinstance(val, dict):
                docs += _namespace_docs(ns, val, lang, site_paths)
    return docs


def _namespace_docs(ns: str, val: dict, lang: str, site_paths: list[str]) -> list[dict]:
    # A namespace like "statutory" holds a dozen sub-pages (solas, marpol, loadLine, ...): give each big
    # child its own document and URL so citations point at the right page.
    """One document per namespace, or per sub-page for very large namespaces."""
    parts = {ns: val}
    if word_count(val) > 1200:
        children = {k: v for k, v in val.items() if isinstance(v, dict) and word_count(v) >= 100}
        parts = {**children, ns: {k: v for k, v in val.items() if k not in children}}
    docs = []
    for key, part in parts.items():
        body = render_namespace(part)
        if sum(len(line.split()) for line in body) < 40:
            continue
        url = map_namespace_url(key, site_paths)
        title = namespace_title(key, part)
        docs.append({"url": url, "title": title, "lang": lang, "doc_type": doc_type_from_url(url),
                     "source": f"i18n:{ns}" + (f".{key}" if key != ns else ""), "published_at": None,
                     "lastmod": None, "text": f"# {title}\n\n" + "\n\n".join(body)})
    return docs


def word_count(o) -> int:
    """Total words in a (nested) dictionary value."""
    if isinstance(o, dict):
        return sum(word_count(v) for v in o.values())
    if isinstance(o, list):
        return sum(word_count(v) for v in o)
    return len(str(o).split())


def namespace_title(ns: str, val: dict) -> str:
    """Title of a namespace document (its title key, or the namespace name)."""
    for k in ("title", "heading", "pageTitle", "hero_title", "heroTitle"):
        if isinstance(val.get(k), str) and len(val[k].split()) <= 12:
            return val[k].strip()
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", ns).replace("-", " ").replace("_", " ").title()
