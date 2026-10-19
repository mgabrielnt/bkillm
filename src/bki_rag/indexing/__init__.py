"""Stage 5 - chunks -> searchable index in data/index/ (`index` command).

  contextualize.py  short bilingual description per chunk (contextual retrieval), cached
  store.py          embeddings + BM25 + chunk metadata on disk; the Index used at query time
  pipeline.py       runs contextualisation and builds the index
  inspect.py        look inside the vectors (`vectors` command)
  export.py         vectors to CSV / Excel
"""
from .store import Index, build, tokenize

__all__ = ["Index", "build", "tokenize"]
