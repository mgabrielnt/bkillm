"""Stage 6b - chunks -> grounded answer with [n] citations and a source list.

  answer.py  RAG class: retrieve, build the source block, call the chat model, collect cited sources
"""
from .answer import RAG

__all__ = ["RAG"]
