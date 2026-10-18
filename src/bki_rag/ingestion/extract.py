"""Stage 2 - turn raw files into Markdown documents + metadata.

Sources:
  * CMS JSON (news, articles, events, ESG pages, job postings): Markdown / TipTap bodies.
  * Static pages: the site's i18n dictionary (one namespace per page) taken from the React Server
    Components payload (English) and /locales/id/common.json (Indonesian). Page-specific strings found in
    the RSC tree (e.g. R&D activity pages) are extracted too.
  * PDFs: pymupdf4llm Markdown, one section per page so chunks can cite page numbers.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

from ..core import config as C
from ..core.utils import read_jsonl

# ---------------------------------------------------------------------------
# React Server Components ("flight") payload
# ---------------------------------------------------------------------------


def parse_flight(html: str) -> dict[str, object]:
    """Decode `self.__next_f.push([1, "..."])` rows into {row_id: json | text}."""
    pieces = []
    for raw in re.findall(r"self\.__next_f\.push\((\[.*?\])\)</script>", html, re.S):
        try:
            arr = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if len(arr) > 1 and isinstance(arr[1], str):
            pieces.append(arr[1])
    data = "".join(pieces).encode("utf-8")
    rows: dict[str, object] = {}
    i, n = 0, len(data)
    while i < n:
        m = re.match(rb"([0-9a-f]+):", data[i:i + 16])
        if not m:
            nl = data.find(b"\n", i)
            i = n if nl < 0 else nl + 1
            continue
        rid, j = m.group(1).decode(), i + m.end()
        if data[j:j + 1] == b"T":  # text row: T<hex byte length>,<text>
            comma = data.find(b",", j)
            size = int(data[j + 1:comma], 16)
            rows[rid] = data[comma + 1:comma + 1 + size].decode("utf-8", "replace")
            i = comma + 1 + size
        else:
            nl = data.find(b"\n", j)
            nl = n if nl < 0 else nl
            payload = data[j:nl].decode("utf-8", "replace")
            try:
                rows[rid] = json.loads(payload)
            except json.JSONDecodeError:
                rows[rid] = payload
            i = nl + 1
    return rows


def find_translations(rows: dict[str, object]) -> dict | None:
    """Return the English i18n dictionary ({"translations": {"en": {"common": {...}}}})."""
    stack = list(rows.values())
    while stack:
        o = stack.pop()
        if isinstance(o, dict):
            t = o.get("translations")
            if isinstance(t, dict) and "en" in t:
                return t["en"].get("common", t["en"])
            stack.extend(o.values())
        elif isinstance(o, list):
            stack.extend(o)
    return None


_TEXT_KEYS = {"children", "title", "description", "body", "content", "text", "caption", "subtitle", "heading", "summary"}
_HEADINGS = {"h1": "# ", "h2": "## ", "h3": "### ", "h4": "#### "}


def tree_text(rows: dict[str, object]) -> list[str]:
    """Visible strings of the page's RSC tree (excluding the shared i18n dictionary and metadata)."""
    out: list[str] = []

    def resolve(s: str) -> str | None:
        if s.startswith("$") and s[1:] in rows and isinstance(rows[s[1:]], str):
            return rows[s[1:]]
        return None if s.startswith("$") else s

    def walk(o, prefix: str = ""):
        if isinstance(o, list):
            if len(o) == 4 and o[0] == "$" and isinstance(o[1], str) and isinstance(o[3], dict):
                tag, props = o[1], o[3]
                if tag in ("script", "style", "link", "meta", "title", "noscript", "svg"):
                    return
                walk_props(props, _HEADINGS.get(tag, "- " if tag == "li" else ""))
                return
            for x in o:
                walk(x, prefix)
        elif isinstance(o, dict):
            walk_props(o, prefix)
        elif isinstance(o, str):
            s = resolve(o)
            if s and len(s.strip()) > 1 and not s.startswith(("http", "/")):
                out.append(prefix + s.strip())

    def walk_props(props: dict, prefix: str):
        for k, v in props.items():
            if k in ("translations", "metadata", "className", "style", "href", "src", "alt", "lng", "namespaces"):
                continue
            if isinstance(v, str):
                if k in _TEXT_KEYS:
                    walk(v, prefix)
            else:
                walk(v, prefix)

    for rid, row in rows.items():
        if isinstance(row, (list, dict)):
            walk(row)
    # drop exact consecutive repeats
    return [s for i, s in enumerate(out) if i == 0 or s != out[i - 1]]


# ---------------------------------------------------------------------------
# i18n dictionary -> one Markdown document per page namespace
# ---------------------------------------------------------------------------

_SUFFIX = re.compile(r"(title|heading|subtitle|label|desc|description|text|body|content|intro|note|caption)$", re.I)
_SKIP_NAMESPACES = {"nav", "common", "footer", "header", "auth", "login", "form", "errors", "notFound", "cookie",
                    "search", "pagination", "breadcrumb", "chatbot", "certificate_verification"}


_LABEL_WORDS = {"title", "heading", "subtitle", "label", "desc", "description", "text", "body", "content", "our"}


def _order_kebab(d: dict) -> list[str]:
    """Order for kebab-case keys ("our-vision", "vision-text", "mission-1", "milestone-1964-title").

    The site stores these keys sorted by length, so a label and its text end up far apart. Group keys by their
    topic words (ignoring label words and list indexes), then emit each group as label first, items by index.
    """
    def parts(k: str) -> list[str]:
        return [p for p in re.split(r"[-_]", k.lower()) if p]

    def stem(k: str) -> str:
        return " ".join(p for p in parts(k) if p not in _LABEL_WORDS and not re.fullmatch(r"p?\d{1,2}", p))

    def index(k: str) -> int:
        nums = [int(p.lstrip("p")) for p in parts(k) if re.fullmatch(r"p?\d{1,2}", p)]
        return nums[0] if nums else 0

    def rank(k: str) -> int:
        p = parts(k)
        return 0 if p[0] == "our" or p[-1] in ("title", "heading") else 1 if p[-1] == "subtitle" else 2

    groups: dict[str, list[str]] = {}
    for k in d:
        groups.setdefault(stem(k), []).append(k)
    order = sorted(groups, key=lambda g: (g != "", g != "intro", list(groups).index(g)))
    return [k for g in order for k in sorted(groups[g], key=lambda k: (index(k), rank(k), k))]


def _order(d: dict) -> list[str]:
    if any("-" in k for k in d):
        return _order_kebab(d)
    groups: dict[str, list[str]] = {}
    for k in d:
        groups.setdefault(_SUFFIX.sub("", k).lower() or k, []).append(k)

    def rank(k: str) -> int:
        kl = k.lower()
        return 0 if kl.endswith(("title", "heading")) else 1 if kl.endswith("subtitle") else 2

    first = [g for g in ("", "title", "heading", "subtitle", "intro", "description") if g in groups]
    keys = []
    for g in first + [g for g in groups if g not in first]:
        keys += sorted(groups[g], key=rank)
    return keys


def render_namespace(d: dict, depth: int = 2) -> list[str]:
    lines: list[str] = []
    is_list = all(re.fullmatch(r"\d+", k) for k in d)
    keys = sorted(d, key=int) if is_list else _order(d)
    for k in keys:
        v = d[k]
        if isinstance(v, str):
            v = v.strip()
            if not v or v.startswith(("/", "http")) or "{{" in v and len(v.split()) < 4:
                continue
            if v.startswith("$"):  # unresolved React Server Components reference, not text
                continue
            if is_list:
                lines.append(f"- {v}")
            elif (k.lower().endswith(("title", "heading")) or k.lower().startswith("our-")) \
                    and len(v.split()) <= 14 and not v.endswith("."):
                lines.append(f"{'#' * min(depth + 1, 4)} {v}")
            else:
                lines.append(v)
        elif isinstance(v, dict):
            lines += render_namespace(v, depth + 1)
        elif isinstance(v, list):
            lines += [f"- {x}" for x in v if isinstance(x, str)]
    return lines


def _words(key: str) -> set[str]:
    key = re.sub(r"([a-z])([A-Z])", r"\1 \2", key)
    return {w for w in re.split(r"[^a-zA-Z0-9]+", key.lower()) if w}


# Namespace -> URL overrides where the fuzzy match is ambiguous.
NAMESPACE_URLS: dict[str, str] = {
    "home": "/", "homepage": "/", "hero": "/", "aboutUs": "/company-profile", "companyProfile": "/company-profile",
    "flagStateServices": "/our-services/statutory/statutory-flag-state-services",
    "statutoryFlagState": "/our-services/statutory/statutory-flag-state-services",
    "ismRegister": "/our-services/statutory/international-safety-management/ism-register",
    "ismRegisterSmc": "/our-services/statutory/international-safety-management/ism-register-smc",
    "ispsRegister": "/our-services/statutory/international-ship-port-facility-security/isps-register",
    "ism": "/our-services/statutory/international-safety-management",
    "isps": "/our-services/statutory/international-ship-port-facility-security",
    "psc": "/our-services/statutory/port-state-control", "portStateControl": "/our-services/statutory/port-state-control",
    "mlc": "/our-services/statutory/maritime-labour-convention", "bwm": "/our-services/statutory/ballast-water-management",
    "privacyPolicy": "/privacy-policy/en", "wbs": "/esgrc/wbs", "gcg": "/esgrc/good-corporate-governance",
    "csr": "/esgrc/corporate-social-responsibility", "esgrcCSR": "/esgrc/corporate-social-responsibility",
    "esgrcEnvironment": "/esgrc/environment", "rnd": "/research/rnd", "boc": "/company-profile",
    "countryFile": "/our-services/statutory", "statutory": "/our-services/statutory",
    "csrPage": "/esgrc/corporate-social-responsibility", "environmentPage": "/esgrc/environment",
    "sustainabilityPage": "/sustainability-report", "rulesRegulations": "/research/rnd/bki-rules-regulations",
    "e_certificate_drawer": "/", "register": "/our-services/classification/ship-register",
}


def map_namespace_url(ns: str, site_paths: list[str]) -> str:
    if ns in NAMESPACE_URLS:
        return C.SITE_URL + NAMESPACE_URLS[ns]
    nw = _words(ns)
    best, best_score = "/", 0.0
    for path in site_paths:
        segs = [s for s in path.strip("/").split("/") if s]
        if not segs:
            continue
        last = _words(segs[-1])
        allw = set().union(*(_words(s) for s in segs))
        score = len(nw & last) / len(nw | last) + 0.25 * len(nw & allw) / max(len(nw), 1)
        if score > best_score:
            best, best_score = path, score
    return C.SITE_URL + (best if best_score >= 0.5 else "/")


def page_docs() -> list[dict]:
    manifest = list(read_jsonl(C.MANIFEST))
    site = [m for m in manifest if m["source"] == "site" and m["status"] == "ok" and m["raw_path"].endswith(".html")]
    site_paths = [urlparse(m["url"]).path or "/" for m in site]
    docs: list[dict] = []
    en_dict = None
    for m in site:
        html = (C.ROOT / m["raw_path"]).read_text(encoding="utf-8", errors="replace")
        rows = parse_flight(html)
        # Long strings (e.g. director bios) are "$18"-style references to text rows of the page that renders
        # them, so resolve each page's copy of the dictionary and keep the first resolved value of every key.
        en_dict = _merge_resolved(en_dict, _resolve_refs(find_translations(rows), rows))
        lines = tree_text(rows)
        title = re.search(r"<title>(.*?)</title>", html)
        docs.append({"url": m["url"], "title": (title.group(1) if title else m["url"]).replace(" | BKI", "").strip(),
                     "lang": "en", "doc_type": _doc_type_from_url(m["url"]), "source": "site-tree",
                     "published_at": None, "lastmod": m.get("lastmod"), "text": "\n\n".join(lines)})
    dicts = {"en": en_dict or {}}
    id_path = C.RAW_SITE / "locale_id.json"
    if id_path.exists():
        raw = json.loads(id_path.read_text(encoding="utf-8"))
        dicts["id"] = raw  # the file *is* the "common" namespace
    for lang, d in dicts.items():
        for ns, val in d.items():
            if ns in _SKIP_NAMESPACES or not isinstance(val, dict):
                continue
            # A namespace like "statutory" holds a dozen sub-pages (solas, marpol, loadLine, ...):
            # give each big child its own document and URL so citations point at the right page.
            parts = {ns: val}
            if _word_count(val) > 1200:
                children = {k: v for k, v in val.items() if isinstance(v, dict) and _word_count(v) >= 100}
                parts = {**children, ns: {k: v for k, v in val.items() if k not in children}}
            for key, part in parts.items():
                body = render_namespace(part)
                if sum(len(l.split()) for l in body) < 40:
                    continue
                url = map_namespace_url(key, site_paths)
                title = _ns_title(key, part)
                docs.append({"url": url, "title": title, "lang": lang, "doc_type": _doc_type_from_url(url),
                             "source": f"i18n:{ns}" + (f".{key}" if key != ns else ""), "published_at": None,
                             "lastmod": None, "text": f"# {title}\n\n" + "\n\n".join(body)})
    return docs


def _resolve_refs(o, rows: dict[str, object]):
    if isinstance(o, dict):
        return {k: _resolve_refs(v, rows) for k, v in o.items()}
    if isinstance(o, str) and o.startswith("$") and isinstance(rows.get(o[1:]), str):
        return rows[o[1:]]
    return o


def _merge_resolved(base, new):
    """Deep-merge two copies of the dictionary, preferring real text over unresolved "$ref" strings."""
    if base is None:
        return new
    if isinstance(base, dict) and isinstance(new, dict):
        return {k: _merge_resolved(base.get(k), new.get(k)) if k in base and k in new else base.get(k, new.get(k))
                for k in {**base, **new}}
    if isinstance(base, str) and base.startswith("$") and isinstance(new, str) and not new.startswith("$"):
        return new
    return base


def _word_count(o) -> int:
    if isinstance(o, dict):
        return sum(_word_count(v) for v in o.values())
    if isinstance(o, list):
        return sum(_word_count(v) for v in o)
    return len(str(o).split())


def _ns_title(ns: str, val: dict) -> str:
    for k in ("title", "heading", "pageTitle", "hero_title", "heroTitle"):
        if isinstance(val.get(k), str) and len(val[k].split()) <= 12:
            return val[k].strip()
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", ns).replace("-", " ").replace("_", " ").title()


def _doc_type_from_url(url: str) -> str:
    path = urlparse(url).path
    for prefix, kind in (("/our-services", "service"), ("/news", "news"), ("/articles", "article"),
                         ("/research", "research"), ("/esgrc", "esg"), ("/privacy-policy", "policy"),
                         ("/our-policy", "policy"), ("/events", "event")):
        if path.startswith(prefix):
            return kind
    return "company"


# ---------------------------------------------------------------------------
# CMS
# ---------------------------------------------------------------------------


def tiptap_to_md(node: dict | list | str | None) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        try:
            node = json.loads(node)
        except json.JSONDecodeError:
            return node
    if isinstance(node, list):
        return "".join(tiptap_to_md(n) for n in node)
    t, kids = node.get("type"), node.get("content", [])
    inner = lambda: "".join(tiptap_to_md(k) for k in kids)  # noqa: E731
    if t == "text":
        txt = node.get("text", "")
        marks = {m.get("type") for m in node.get("marks", [])}
        return f"**{txt}**" if "bold" in marks and txt.strip() else txt
    if t == "heading":
        return "#" * min(node.get("attrs", {}).get("level", 2) + 1, 4) + " " + inner().replace("**", "") + "\n\n"
    if t == "paragraph":
        return inner() + "\n\n"
    if t == "hardBreak":
        return "\n"
    if t in ("bulletList", "orderedList"):
        out = []
        for i, li in enumerate(kids, 1):
            bullet = f"{i}." if t == "orderedList" else "-"
            out.append(f"{bullet} " + tiptap_to_md(li).strip().replace("\n\n", "\n  "))
        return "\n".join(out) + "\n\n"
    if t == "table":
        rows = [[tiptap_to_md(c).strip().replace("\n", " ").replace("|", "/") for c in r.get("content", [])] for r in kids]
        if not rows:
            return ""
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        md = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width] + ["| " + " | ".join(r) + " |" for r in rows[1:]]
        return "\n".join(md) + "\n\n"
    if t in ("image", "horizontalRule"):
        return "\n"
    return inner()


def _blocks_md(blocks: list[dict]) -> str:
    parts = []
    for b in blocks or []:
        for key in ("body", "content", "text"):
            if isinstance(b.get(key), str) and b[key].strip():
                parts.append(b[key].strip())
    return "\n\n".join(parts)


ESG_URLS = {"environment": "/esgrc/environment", "social": "/esgrc/corporate-social-responsibility",
            "governance": "/esgrc/good-corporate-governance"}


def cms_docs() -> list[dict]:
    docs = []

    def load(name: str) -> list[dict]:
        p = C.RAW_CMS / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []

    for lang in ("en", "id"):
        for it in load(f"newss_{lang}.json"):
            title = it["title"].strip()
            ann = re.search(r"pengumuman|announcement|seleksi|selection|rekrutmen|recruitment|tender", title, re.I)
            docs.append({"url": f"{C.SITE_URL}/news/{it['slug']}", "title": title, "lang": lang,
                         "doc_type": "announcement" if ann else "news", "source": "cms:news", "group_id": it.get("documentId"),
                         "published_at": it.get("publishedAt"), "lastmod": it.get("updatedAt"),
                         "text": f"# {title}\n\n{(it.get('description') or '').strip()}\n\n{_blocks_md(it.get('blocks'))}"})
        for it in load(f"articles_{lang}.json"):
            author = (it.get("author") or {}).get("name") if isinstance(it.get("author"), dict) else None
            docs.append({"url": f"{C.SITE_URL}/articles/{it['slug']}", "title": it["title"].strip(), "lang": lang,
                         "doc_type": "article", "source": "cms:article", "group_id": it.get("documentId"), "published_at": it.get("publishedAt"),
                         "lastmod": it.get("updatedAt"),
                         "text": f"# {it['title'].strip()}\n\n" + (f"Author: {author}\n\n" if author else "")
                                 + f"{(it.get('description') or '').strip()}\n\n{_blocks_md(it.get('blocks'))}"})
        for it in load(f"events_{lang}.json"):
            meta = f"Location: {it.get('location') or '-'}; Date: {it.get('startDate') or '-'}"
            docs.append({"url": f"{C.SITE_URL}/events/{it['slug']}", "title": it["title"].strip(), "lang": lang,
                         "doc_type": "event", "source": "cms:event", "group_id": it.get("documentId"), "published_at": it.get("publishedAt"),
                         "lastmod": it.get("updatedAt"),
                         "text": f"# {it['title'].strip()}\n\n{meta}\n\n{(it.get('description') or '').strip()}\n\n{_blocks_md(it.get('blocks'))}"})
        for it in load(f"keberlanjutans_{lang}.json"):
            menu = it.get("menu_keberlanjutan") or {}
            section = (menu.get("name") or "").split("-")[0].split("=")[0]
            label = menu.get("label_en" if lang == "en" else "label_id") or ""
            body = tiptap_to_md(it.get("content_tiptap")) or (it.get("content") or "")
            title = it["title"].strip()
            heading = f"# ESG > {section.title() or 'Sustainability'}" + (f" > {label}" if label else "") + f": {title}"
            docs.append({"url": C.SITE_URL + ESG_URLS.get(section, "/esgrc/corporate-social-responsibility"),
                         "title": title, "lang": lang, "doc_type": "esg", "source": "cms:esg", "group_id": it.get("documentId"),
                         "published_at": it.get("publishedAt"), "lastmod": it.get("updatedAt"),
                         "text": f"{heading}\n\n{body}"})
    for it in load("job-postings_all.json"):
        docs.append({"url": f"{C.SITE_URL}/opportunities", "title": it["title"].strip(), "lang": "id",
                     "doc_type": "job", "source": "cms:job", "published_at": it.get("publishedAt"),
                     "lastmod": it.get("updatedAt"),
                     "text": f"# Lowongan: {it['title'].strip()}\n\nLokasi: {it.get('location') or '-'}\n\n{_blocks_md(it.get('blocks'))}"})
    return docs


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------


def pdf_docs() -> list[dict]:
    import pymupdf4llm

    docs = []
    for m in read_jsonl(C.MANIFEST):
        if m["source"] != "pdf" or m["status"] != "ok":
            continue
        path = C.ROOT / m["raw_path"]
        cache = C.CACHE_DIR / f"pdf_{m['sha256'][:16]}.json"  # PDF parsing is the slow step: do it once
        if cache.exists():
            pages = json.loads(cache.read_text(encoding="utf-8"))
        else:
            print(f"[extract] pdf {m['title']} ({m.get('size_mb')} MB) ...", flush=True)
            pages = pymupdf4llm.to_markdown(str(path), page_chunks=True, show_progress=False,
                                            ignore_images=True, ignore_graphics=True)
            pages = [{"metadata": {"page": (p.get("metadata") or {}).get("page")}, "text": p["text"]} for p in pages]
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
        kind = {"annual-reports": "annual_report", "sustainability-reports": "sustainability_report"}.get(m["collection"], "policy")
        title = {"annual_report": f"BKI Annual Report {m['year']}",
                 "sustainability_report": f"BKI {m['title']}"}.get(kind, Path(m["title"]).stem.replace("-", " ").replace("_", " "))
        docs.append({"url": m["url"], "title": title, "lang": None, "doc_type": kind, "source": "pdf",
                     "published_at": f"{m['year']}-12-31" if m.get("year") else None, "lastmod": None,
                     "pages": [{"page": (p.get("metadata") or {}).get("page") or i + 1, "text": p["text"]}
                               for i, p in enumerate(pages)]})
    return docs
