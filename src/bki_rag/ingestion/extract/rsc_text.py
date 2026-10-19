"""Visible text of a page's React Server Components tree (headings, paragraphs, list items).

Used for page-specific content that is not in the i18n dictionary. Navigation and footer strings are
extracted too; the cleaning stage removes them because they repeat on every page.
"""
from __future__ import annotations

_TEXT_KEYS = {"children", "title", "description", "body", "content", "text", "caption", "subtitle", "heading",
              "summary"}
_SKIP_PROPS = {"translations", "metadata", "className", "style", "href", "src", "alt", "lng", "namespaces"}
_SKIP_TAGS = {"script", "style", "link", "meta", "title", "noscript", "svg"}
_HEADINGS = {"h1": "# ", "h2": "## ", "h3": "### ", "h4": "#### "}


# Teks dari pohon elemen halaman, dengan awalan heading / butir Markdown.
def tree_text(rows: dict[str, object]) -> list[str]:
    out: list[str] = []

    # Teks di balik "$ref", string itu sendiri, atau None untuk referensi lain.
    def resolve(s: str) -> str | None:
        if s.startswith("$") and s[1:] in rows and isinstance(rows[s[1:]], str):
            return rows[s[1:]]
        return None if s.startswith("$") else s

    # Kumpulkan teks dari node mana pun di pohon.
    def walk(o, prefix: str = ""):
        if isinstance(o, list):
            if len(o) == 4 and o[0] == "$" and isinstance(o[1], str) and isinstance(o[3], dict):
                tag, props = o[1], o[3]  # elemen React: ["$", tag, key, props]
                if tag not in _SKIP_TAGS:
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

    # Kumpulkan teks dari props sebuah elemen, lewati styling dan metadata.
    def walk_props(props: dict, prefix: str):
        for k, v in props.items():
            if k in _SKIP_PROPS:
                continue
            if not isinstance(v, str) or k in _TEXT_KEYS:
                walk(v, prefix)

    for row in rows.values():
        if isinstance(row, (list, dict)):
            walk(row)
    return [s for i, s in enumerate(out) if i == 0 or s != out[i - 1]]  # buang pengulangan berturut-turut
