"""Thin OpenAI wrapper (gpt-5-nano for text, text-embedding-3-large for vectors) + a thread-pool map."""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Callable, Iterable, TypeVar

import numpy as np
from openai import OpenAI, RateLimitError

from . import config as C

T = TypeVar("T")
R = TypeVar("R")
_USAGE = {"llm_in": 0, "llm_out": 0, "embed": 0}  # token terpakai sejak program mulai (untuk hitung biaya)
_USAGE_LOCK = threading.Lock()


# Tambahkan jumlah token ke penghitung pemakaian.
def _track(key: str, tokens: int | None) -> None:
    with _USAGE_LOCK:
        _USAGE[key] += tokens or 0


# Salinan penghitung token: {"llm_in", "llm_out", "embed"}.
def usage() -> dict:
    with _USAGE_LOCK:
        return dict(_USAGE)


# Biaya dalam USD dari selisih dua salinan penghitung token (harga per 1 juta token di config).
def cost_usd(before: dict, after: dict) -> float:
    return sum((after[k] - before[k]) * C.PRICE_PER_1M_TOKENS[k] / 1e6 for k in _USAGE)


# Client OpenAI-compatible yang dipakai bersama (base URL dan key dari config).
@lru_cache(maxsize=1)
def client() -> OpenAI:
    return OpenAI(base_url=C.BASE_URL, max_retries=3, timeout=120)


# Satu panggilan chat ke model; menunggu lalu mencoba lagi jika kena batas laju akun.
def chat(messages: list[dict], reasoning: str = C.HELPER_REASONING, json_mode: bool = False,
         max_tokens: int | None = None) -> str:
    kwargs: dict = {"model": C.LLM_MODEL, "messages": messages, "reasoning_effort": reasoning}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if max_tokens:
        kwargs["max_completion_tokens"] = max_tokens
    for attempt in range(8):  # batas token/menit akun ketat untuk pekerjaan massal: tunggu lalu coba lagi
        try:
            resp = client().chat.completions.create(**kwargs)
            if resp.usage:
                _track("llm_in", resp.usage.prompt_tokens)
                _track("llm_out", resp.usage.completion_tokens)
            return resp.choices[0].message.content or ""
        except RateLimitError:
            if attempt == 7:
                raise
            time.sleep(min(60, 5 * 2 ** attempt))
    return ""


# Panggilan chat yang harus menghasilkan JSON; {} jika gagal setelah 3 percobaan.
def chat_json(messages: list[dict], reasoning: str = C.HELPER_REASONING) -> dict:
    for attempt in range(3):
        try:
            return json.loads(chat(messages, reasoning=reasoning, json_mode=True))
        except json.JSONDecodeError:
            time.sleep(1 + attempt)
    return {}


# Ubah teks menjadi vektor per batch; hasilnya dinormalisasi (panjang 1), satu baris per teks.
def embed(texts: list[str], model: str = C.EMBED_MODEL, batch: int = 128) -> np.ndarray:
    out: list[list[float]] = []
    for i in range(0, len(texts), batch):
        resp = client().embeddings.create(model=model, input=[t[:30000] for t in texts[i:i + batch]])
        _track("embed", resp.usage.total_tokens if resp.usage else 0)
        out += [d.embedding for d in resp.data]
    arr = np.asarray(out, dtype=np.float32)
    return arr / np.linalg.norm(arr, axis=1, keepdims=True)


# Jalankan fn untuk setiap item secara paralel (thread), urutan hasil sama dengan input.
def pmap(fn: Callable[[T], R], items: Iterable[T], workers: int = C.LLM_CONCURRENCY, desc: str = "") -> list[R]:
    items = list(items)
    results: list[R] = [None] * len(items)  # type: ignore[list-item]
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(fn, it): i for i, it in enumerate(items)}
        for fut in futures:
            results[futures[fut]] = fut.result()
            done += 1
            if desc and (done % 50 == 0 or done == len(items)):
                print(f"  {desc}: {done}/{len(items)}", flush=True)
    return results
