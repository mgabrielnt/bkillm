"""Duplicate removal: exact (sha256 of normalised text), then near-duplicates (MinHash LSH).

Near-duplicates use 5-word shingles and Jaccard >= 0.8. A dropped duplicate's URL is kept as an
alias of the surviving document.
"""
from __future__ import annotations

import re

from datasketch import MinHash, MinHashLSH

from ...core.utils import sha256
from .filters import norm_block


def _minhash(text: str) -> MinHash:
    words = re.findall(r"\w+", text.lower())
    m = MinHash(num_perm=128)
    for i in range(max(1, len(words) - 4)):
        m.update(" ".join(words[i:i + 5]).encode("utf-8"))
    return m


def _add_alias(keep: dict, dup: dict) -> None:
    if dup["url"] != keep["url"]:
        keep.setdefault("aliases", []).append(dup["url"])


def dedup(docs: list[dict]) -> tuple[list[dict], int, int]:
    """Returns (kept docs, number of exact duplicates, number of near-duplicates)."""
    by_hash: dict[str, dict] = {}
    exact = 0
    for d in docs:
        h = sha256(norm_block(d["full_text"]))
        if h in by_hash:
            _add_alias(by_hash[h], d)
            exact += 1
        else:
            by_hash[h] = d
    lsh = MinHashLSH(threshold=0.8, num_perm=128)
    kept: list[dict] = []
    near = 0
    for d in sorted(by_hash.values(), key=lambda x: -len(x["full_text"])):  # keep the longest version
        mh = _minhash(d["full_text"])
        hits = lsh.query(mh)
        if hits:
            _add_alias(kept[hits[0]], d)
            near += 1
            continue
        lsh.insert(len(kept), mh)
        kept.append(d)
    return kept, exact, near
