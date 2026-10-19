"""Stage 4 - structure-aware chunking with breadcrumbs and citation metadata.

Modules:
  units.py    paragraph units with heading paths; splitting oversized tables/paragraphs; language
  chunker.py  packing units into chunks and building the chunk records
"""
from .chunker import chunk_document

__all__ = ["chunk_document"]
