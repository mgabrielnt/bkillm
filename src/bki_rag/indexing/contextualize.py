"""Contextual retrieval: a short, bilingual description of where each chunk sits in its document.

Results are cached by chunk content hash (data/cache/context_<model>.jsonl) and appended as they arrive,
so an interrupted run resumes where it stopped and re-runs only pay for new chunks.
"""
from __future__ import annotations

import json
import threading

from ..core import config as C
from ..core.llm import chat, pmap
from ..core.utils import read_jsonl, truncate_tokens
from ..prompts import CONTEXT_PROMPT, GLOSSARY


def _document_window(chunk: dict, doc_chunks: list[dict]) -> str:
    """The whole document if it is short, otherwise the neighbouring chunks (~CONTEXT_WINDOW_TOKENS)."""
    if sum(c["tokens"] for c in doc_chunks) <= C.CONTEXT_WINDOW_TOKENS:
        return "\n\n".join(c["text"] for c in doc_chunks)
    i = chunk["chunk_index"]
    lo, hi, budget = i, i, chunk["tokens"]
    while budget < C.CONTEXT_WINDOW_TOKENS and (lo > 0 or hi < len(doc_chunks) - 1):
        if lo > 0:
            lo -= 1
            budget += doc_chunks[lo]["tokens"]
        if hi < len(doc_chunks) - 1:
            hi += 1
            budget += doc_chunks[hi]["tokens"]
    return "[...]\n\n" + "\n\n".join(c["text"] for c in doc_chunks[lo:hi + 1]) + "\n\n[...]"


def describe_chunk(chunk: dict, doc_chunks: list[dict]) -> str:
    prompt = CONTEXT_PROMPT.format(
        title=chunk["title"], url=chunk["url"], doc_type=chunk["doc_type"], chunk=chunk["text"], glossary=GLOSSARY,
        document=truncate_tokens(_document_window(chunk, doc_chunks), C.CONTEXT_WINDOW_TOKENS + 1500))
    return chat([{"role": "user", "content": prompt}], model=C.CONTEXT_MODEL, reasoning=C.CONTEXT_REASONING).strip()


def add_context(chunks: list[dict]) -> None:
    """Set chunk["context"] for every chunk, calling the model only for uncached ones."""
    cache_file = C.CACHE_DIR / f"context_{C.CONTEXT_MODEL}.jsonl"
    cache = {r["hash"]: r["context"] for r in read_jsonl(cache_file)} if cache_file.exists() else {}
    by_doc: dict[str, list[dict]] = {}
    for c in chunks:
        by_doc.setdefault(c["doc_id"], []).append(c)
    for cs in by_doc.values():
        cs.sort(key=lambda x: x["chunk_index"])
    todo = [c for c in chunks if c["content_hash"] not in cache]
    print(f"[index] contextualising {len(todo)} chunks ({len(chunks) - len(todo)} cached) with {C.CONTEXT_MODEL}")
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()

    def work(c: dict) -> None:
        ctx = describe_chunk(c, by_doc[c["doc_id"]])
        with lock:
            cache[c["content_hash"]] = ctx
            with open(cache_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({"hash": c["content_hash"], "context": ctx}, ensure_ascii=False) + "\n")

    pmap(work, todo, workers=8, desc="context")  # 8 workers stays under a 2M tokens/min account limit
    for c in chunks:
        c["context"] = cache.get(c["content_hash"], "")
