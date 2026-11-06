"""Thin OpenAI wrapper: chat (plain, streaming, JSON) and embeddings, with retries."""
from __future__ import annotations

import json
import time
from functools import lru_cache
from typing import Iterator

import numpy as np
from openai import OpenAI, RateLimitError

from . import config as C
from .usage import track


# Client OpenAI-compatible yang dipakai bersama (base URL dan key dari config).
@lru_cache(maxsize=1)
def client() -> OpenAI:
    return OpenAI(base_url=C.BASE_URL, max_retries=3, timeout=120)


# Kirim permintaan chat; menunggu lalu mencoba lagi jika kena batas laju akun.
def _create(**kwargs):
    for attempt in range(8):  # batas token/menit akun ketat untuk pekerjaan massal: tunggu lalu coba lagi
        try:
            return client().chat.completions.create(**kwargs)
        except RateLimitError:
            if attempt == 7:
                raise
            time.sleep(min(60, 5 * 2 ** attempt))
    raise RuntimeError("unreachable")


# Argumen permintaan chat yang sama untuk mode biasa dan streaming.
def _chat_args(messages: list[dict], reasoning: str, verbosity: str) -> dict:
    kwargs: dict = {"model": C.LLM_MODEL, "messages": messages, "reasoning_effort": reasoning}
    if verbosity:
        kwargs["verbosity"] = verbosity
    return kwargs


# Catat pemakaian token dari satu response.
def _track_usage(info) -> None:
    if info:
        track("llm_in", info.prompt_tokens)
        track("llm_out", info.completion_tokens)


# Satu panggilan chat ke model; mengembalikan seluruh teks sekaligus.
def chat(messages: list[dict], reasoning: str = C.HELPER_REASONING, json_mode: bool = False,
         max_tokens: int | None = None, verbosity: str = "") -> str:
    kwargs = _chat_args(messages, reasoning, verbosity)
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if max_tokens:
        kwargs["max_completion_tokens"] = max_tokens
    resp = _create(**kwargs)
    _track_usage(resp.usage)
    return resp.choices[0].message.content or ""


# Panggilan chat streaming: menghasilkan potongan teks begitu dikirim model.
def chat_stream(messages: list[dict], reasoning: str = C.HELPER_REASONING, verbosity: str = "") -> Iterator[str]:
    kwargs = _chat_args(messages, reasoning, verbosity)
    for event in _create(**kwargs, stream=True, stream_options={"include_usage": True}):
        _track_usage(event.usage)
        if event.choices and event.choices[0].delta.content:
            yield event.choices[0].delta.content


# Panggilan chat yang harus menghasilkan JSON; {} jika gagal setelah 3 percobaan.
def chat_json(messages: list[dict], reasoning: str = C.HELPER_REASONING) -> dict:
    for attempt in range(3):
        try:
            return json.loads(chat(messages, reasoning=reasoning, json_mode=True))
        except json.JSONDecodeError:
            time.sleep(1 + attempt)
    return {}


# Ubah teks menjadi vektor per batch; hasilnya dinormalisasi (panjang 1), satu baris per teks.
def embed(texts: list[str], model: str = C.EMBED_MODEL, batch: int = 128, timeout: float | None = None) -> np.ndarray:
    api = client().with_options(timeout=timeout) if timeout else client()
    out: list[list[float]] = []
    for i in range(0, len(texts), batch):
        resp = api.embeddings.create(model=model, input=[t[:30000] for t in texts[i:i + batch]])
        track("embed", resp.usage.total_tokens if resp.usage else 0)
        out += [d.embedding for d in resp.data]
    arr = np.asarray(out, dtype=np.float32)
    return arr / np.linalg.norm(arr, axis=1, keepdims=True)
