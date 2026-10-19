"""Decode the React Server Components ("flight") payload that Next.js embeds in every page.

The payload is a list of rows `<hex id>:<json>` or `<hex id>:T<hex byte length>,<text>`. Long strings in
the tree are references like "$18" that point to a text row.
"""
from __future__ import annotations

import json
import re


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
    """The English i18n dictionary inside the payload ({"translations": {"en": {"common": {...}}}})."""
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


def resolve_refs(o, rows: dict[str, object]):
    """Replace "$18"-style references with the text row they point to (when this page has it)."""
    if isinstance(o, dict):
        return {k: resolve_refs(v, rows) for k, v in o.items()}
    if isinstance(o, str) and o.startswith("$") and isinstance(rows.get(o[1:]), str):
        return rows[o[1:]]
    return o


def merge_resolved(base, new):
    """Deep-merge two copies of the dictionary, preferring real text over unresolved "$ref" strings."""
    if base is None:
        return new
    if isinstance(base, dict) and isinstance(new, dict):
        return {k: merge_resolved(base.get(k), new.get(k)) if k in base and k in new else base.get(k, new.get(k))
                for k in {**base, **new}}
    if isinstance(base, str) and base.startswith("$") and isinstance(new, str) and not new.startswith("$"):
        return new
    return base
