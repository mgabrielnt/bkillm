"""Look inside the vector index (`python -m bki_rag vectors`).

Files in data/index/:
  embeddings.npy  float32 matrix, one row per chunk (1840 x 3072 for text-embedding-3-large), each row
                  L2-normalised so a dot product is the cosine similarity
  chunks.jsonl    the chunk for each row, in the same order (row i of the matrix = line i of this file)
  meta.json       embedding model and whether contextual retrieval was used
  bm25/           the keyword (BM25) index over the same chunks
Everything here is free (no API calls) except --query, which embeds your text once.
"""
from __future__ import annotations

import csv

import numpy as np

from ..core import config as C
from ..core.llm import embed
from .store import Index


def _row(ix: Index, chunk_id: str | None) -> int:
    """Matrix row of a chunk id (row 0 when no id is given)."""
    if not chunk_id:
        return 0
    for i, c in enumerate(ix.chunks):
        if c["chunk_id"] == chunk_id:
            return i
    raise SystemExit(f"chunk id not found: {chunk_id}")


def _print_neighbours(ix: Index, vec: np.ndarray, k: int, skip: int | None = None) -> None:
    """The k chunks whose vectors are closest (highest cosine similarity) to `vec`."""
    scores = ix.emb @ vec
    shown = 0
    for i in np.argsort(-scores):
        if i == skip:
            continue
        c = ix.chunks[i]
        print(f"  {scores[i]:.3f}  {c['chunk_id']:34s} {c['title'][:60]}")
        shown += 1
        if shown == k:
            break


def show(chunk_id: str | None = None, query: str | None = None, dims: int = 8, k: int = 5,
         export: str | None = None, rows: int = 20) -> None:
    """Print index facts, one chunk's vector and its nearest chunks; optionally export vectors to CSV."""
    ix = Index()
    print(f"embeddings.npy : {ix.emb.shape[0]} rows x {ix.emb.shape[1]} dims, {ix.emb.dtype}, "
          f"model {ix.meta['embed_model']}, contextual={ix.meta['contextual']}")
    print(f"chunks.jsonl   : {len(ix.chunks)} chunks (row i = line i)\n")
    if query:
        vec = embed([query], model=ix.meta["embed_model"])[0]
        print(f"query: {query!r}\nfirst {dims} dims: {[round(float(x), 4) for x in vec[:dims]]}\nnearest chunks:")
        _print_neighbours(ix, vec, k)
    else:
        i = _row(ix, chunk_id)
        c, vec = ix.chunks[i], ix.emb[i]
        print(f"row {i}: {c['chunk_id']} | {c['title']}\n{c['url']}\n")
        print(c["text"][:400].replace("\n", " ") + " ...\n")
        print(f"vector (first {dims} of {len(vec)} dims): {[round(float(x), 4) for x in vec[:dims]]}")
        print(f"vector length (norm): {np.linalg.norm(vec):.3f}\nnearest chunks:")
        _print_neighbours(ix, vec, k, skip=i)
    if export:
        _export(ix, export, rows)


def _export(ix: Index, path: str, rows: int) -> None:
    """Write the first `rows` chunks and their full vectors to CSV (opens in Excel / Sheets)."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["chunk_id", "title", "url"] + [f"d{j}" for j in range(ix.emb.shape[1])])
        for c, vec in zip(ix.chunks[:rows], ix.emb[:rows]):
            w.writerow([c["chunk_id"], c["title"], c["url"]] + [f"{x:.6f}" for x in vec])
    print(f"\nexported {min(rows, len(ix.chunks))} rows to {path} (index dir: {C.INDEX_DIR})")
