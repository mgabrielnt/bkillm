"""Thin OpenAI wrapper: chat, JSON chat, embeddings, and a thread-pool map with retries."""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Callable, Iterable, TypeVar

import numpy as np
from openai import OpenAI, RateLimitError

from . import config as C

T = TypeVar("T")
R = TypeVar("R")


@lru_cache(maxsize=1)
def client() -> OpenAI:
    """Shared OpenAI-compatible client (base URL and key come from config)."""
    return OpenAI(base_url=C.BASE_URL, max_retries=3, timeout=120)


def chat(messages: list[dict], model: str = C.FAST_MODEL, reasoning: str | None = None,
         json_mode: bool = False, max_tokens: int | None = None) -> str:
    """One chat completion; backs off and retries when the account rate limit is hit."""
    kwargs: dict = {"model": model, "messages": messages}
    effort = reasoning if reasoning is not None else (C.FAST_REASONING if model == C.FAST_MODEL else C.CHAT_REASONING)
    if effort:
        kwargs["reasoning_effort"] = effort
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if max_tokens:
        kwargs["max_completion_tokens"] = max_tokens
    for attempt in range(8):  # account TPM limits are tight for bulk jobs: back off and retry
        try:
            resp = client().chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""
        except RateLimitError:
            if attempt == 7:
                raise
            time.sleep(min(60, 5 * 2 ** attempt))
    return ""


def chat_json(messages: list[dict], model: str = C.FAST_MODEL, reasoning: str | None = None) -> dict:
    """Chat completion that must return JSON; {} if the model fails to after 3 tries."""
    for attempt in range(3):
        try:
            return json.loads(chat(messages, model=model, reasoning=reasoning, json_mode=True))
        except json.JSONDecodeError:
            time.sleep(1 + attempt)
    return {}


def embed(texts: list[str], model: str = C.EMBED_MODEL, batch: int = 128) -> np.ndarray:
    """Embed texts in batches; returns L2-normalised vectors, one row per text."""
    out: list[list[float]] = []
    for i in range(0, len(texts), batch):
        resp = client().embeddings.create(model=model, input=[t[:30000] for t in texts[i:i + batch]])
        out += [d.embedding for d in resp.data]
    arr = np.asarray(out, dtype=np.float32)
    return arr / np.linalg.norm(arr, axis=1, keepdims=True)


def pmap(fn: Callable[[T], R], items: Iterable[T], workers: int = C.LLM_CONCURRENCY, desc: str = "") -> list[R]:
    """Run fn over items in parallel threads, keeping the input order."""
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
