"""Stage 6b - chunks -> grounded answer with [n] citations and a matching source list.

  sources.py    the <sources> block for the model (title, URL, how current, context, content)
  reply.py      ask the chat model: streaming, and a careful second try when it refuses
  citations.py  clean up and renumber citations; readable source titles
  answer.py     RAG class: retrieve, ask the chat model, return answer + sources
"""
from .answer import RAG

__all__ = ["RAG"]
