"""Render one namespace of the site's i18n dictionary as readable Markdown.

The dictionary stores a page's texts as flat keys sorted by length, so a label ("our-vision") and its text
("vision-text") end up far apart. Keys are regrouped by topic and emitted label first, then items in order.
"""
from __future__ import annotations

import re

_SUFFIX = re.compile(r"(title|heading|subtitle|label|desc|description|text|body|content|intro|note|caption)$", re.I)
_LABEL_WORDS = {"title", "heading", "subtitle", "label", "desc", "description", "text", "body", "content", "our"}


def _order_kebab(d: dict) -> list[str]:
    """Order for kebab-case keys ("our-vision", "vision-text", "mission-1", "milestone-1964-title")."""
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


def _order_camel(d: dict) -> list[str]:
    """Order for camelCase keys ("pathTitle", "pathDesc"): group by stem, title before text."""
    groups: dict[str, list[str]] = {}
    for k in d:
        groups.setdefault(_SUFFIX.sub("", k).lower() or k, []).append(k)

    def rank(k: str) -> int:
        kl = k.lower()
        return 0 if kl.endswith(("title", "heading")) else 1 if kl.endswith("subtitle") else 2

    first = [g for g in ("", "title", "heading", "subtitle", "intro", "description") if g in groups]
    return [k for g in first + [g for g in groups if g not in first] for k in sorted(groups[g], key=rank)]


def _is_heading(key: str, value: str) -> bool:
    k = key.lower()
    return (k.endswith(("title", "heading")) or k.startswith("our-")) and len(value.split()) <= 14 \
        and not value.endswith(".")


def render_namespace(d: dict, depth: int = 2) -> list[str]:
    """Markdown lines (headings, paragraphs, bullets) for one namespace or sub-dictionary."""
    lines: list[str] = []
    is_list = all(re.fullmatch(r"\d+", k) for k in d)
    keys = sorted(d, key=int) if is_list else _order_kebab(d) if any("-" in k for k in d) else _order_camel(d)
    for k in keys:
        v = d[k]
        if isinstance(v, str):
            v = v.strip()
            if not v or v.startswith(("/", "http", "$")) or "{{" in v and len(v.split()) < 4:
                continue  # empty, a link, an unresolved reference or a template fragment
            if is_list:
                lines.append(f"- {v}")
            elif _is_heading(k, v):
                lines.append(f"{'#' * min(depth + 1, 4)} {v}")
            else:
                lines.append(v)
        elif isinstance(v, dict):
            lines += render_namespace(v, depth + 1)
        elif isinstance(v, list):
            lines += [f"- {x}" for x in v if isinstance(x, str)]
    return lines


def word_count(o) -> int:
    if isinstance(o, dict):
        return sum(word_count(v) for v in o.values())
    if isinstance(o, list):
        return sum(word_count(v) for v in o)
    return len(str(o).split())


def namespace_title(ns: str, val: dict) -> str:
    for k in ("title", "heading", "pageTitle", "hero_title", "heroTitle"):
        if isinstance(val.get(k), str) and len(val[k].split()) <= 12:
            return val[k].strip()
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", ns).replace("-", " ").replace("_", " ").title()
