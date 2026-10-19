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


# Baca file JSONL, satu dict per baris.
def read_jsonl(path: Path) -> Iterator[dict]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


# Tulis daftar dict ke file JSONL (satu per baris); mengembalikan jumlah baris.
def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return n


# Hash SHA-256 dari teks atau bytes (untuk deteksi duplikat dan cache).
def sha256(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


# Tokenizer tiktoken untuk menghitung token (dimuat sekali).
@lru_cache(maxsize=1)
def _encoder():
    return tiktoken.get_encoding("o200k_base")


# Jumlah token dalam sebuah teks (o200k_base).
def count_tokens(text: str) -> int:
    return len(_encoder().encode(text, disallowed_special=()))


# Potong teks menjadi maksimal max_tokens token.
def truncate_tokens(text: str, max_tokens: int) -> str:
    enc = _encoder()
    ids = enc.encode(text, disallowed_special=())
    return text if len(ids) <= max_tokens else enc.decode(ids[:max_tokens])


_CONTROL = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f​﻿]")


# Rapikan teks: NFKC, buang karakter kontrol, sambung kata terpotong di PDF, padatkan baris kosong.
def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL.sub("", text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
