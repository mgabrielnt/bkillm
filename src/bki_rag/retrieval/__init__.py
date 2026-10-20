"""Stage 6a - question -> most relevant chunks.

  restricted.py rules & regulations questions -> login link only (keyword check, no search)
  query.py      rewrite the question: standalone, English, Indonesian, keywords, language
  retriever.py  vector + BM25 search for every variant, merged with Reciprocal Rank Fusion
"""
from .retriever import Retriever

__all__ = ["Retriever"]
