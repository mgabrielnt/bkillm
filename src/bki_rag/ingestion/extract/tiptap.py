"""Convert CMS rich text to Markdown: TipTap JSON documents (ESG pages) and Strapi content blocks."""
from __future__ import annotations

import json


# Markdown dari dokumen TipTap (judul, paragraf, tebal, daftar, tabel).
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

    # Markdown dari anak-anak node ini.
    def inner() -> str:
        return "".join(tiptap_to_md(k) for k in kids)

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
        items = [f"{f'{i}.' if t == 'orderedList' else '-'} " + tiptap_to_md(li).strip().replace("\n\n", "\n  ")
                 for i, li in enumerate(kids, 1)]
        return "\n".join(items) + "\n\n"
    if t == "table":
        return _table_md(kids)
    if t in ("image", "horizontalRule"):
        return "\n"
    return inner()


# Tabel Markdown dari baris-baris tabel TipTap.
def _table_md(rows_nodes: list[dict]) -> str:
    rows = [[tiptap_to_md(c).strip().replace("\n", " ").replace("|", "/") for c in r.get("content", [])]
            for r in rows_nodes]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    md = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width] + ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(md) + "\n\n"


# Teks dari blok dinamis Strapi (isi rich-text sudah berupa Markdown).
def blocks_md(blocks: list[dict] | None) -> str:
    parts = []
    for b in blocks or []:
        for key in ("body", "content", "text"):
            if isinstance(b.get(key), str) and b[key].strip():
                parts.append(b[key].strip())
    return "\n\n".join(parts)
