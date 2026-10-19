"""Small shared helpers: JSONL IO, hashing, token counting, text normalisation."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Iterator

import tiktoken


def read_jsonl(path: Path) -> Iterator[dict]:
    """Yield one dict per line of a JSONL file."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    """Write dicts as JSONL, one per line; returns the number of rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return n


def sha256(data: str | bytes) -> str:
    """Hex SHA-256 of a string or bytes (used for dedup and caching)."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


@lru_cache(maxsize=1)
def _encoder():
    """The tiktoken tokenizer used for counting (loaded once)."""
    return tiktoken.get_encoding("o200k_base")


def count_tokens(text: str) -> int:
    """Number of tokens in a text (o200k_base)."""
    return len(_encoder().encode(text, disallowed_special=()))


def truncate_tokens(text: str, max_tokens: int) -> str:
    """Cut a text to at most max_tokens tokens."""
    enc = _encoder()
    ids = enc.encode(text, disallowed_special=())
    return text if len(ids) <= max_tokens else enc.decode(ids[:max_tokens])


_CONTROL = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f​﻿]")


def normalize_text(text: str) -> str:
    """NFKC, strip control chars, join hyphenated PDF line breaks, collapse blank lines."""
    text = unicodedata.normalize("NFKC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL.sub("", text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
