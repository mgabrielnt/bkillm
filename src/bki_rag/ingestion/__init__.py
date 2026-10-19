"""Stages 1-4: from the website to clean, citable chunks (`crawl`, then `process`).

Subpackages / modules:
  crawl/       Stage 1  download raw pages, CMS data and PDFs into data/raw/
  extract/     Stage 2  raw files -> Markdown documents with metadata
  clean/       Stage 3  boilerplate removal, normalisation, de-duplication
  chunk/       Stage 4  structure-aware chunks with breadcrumbs
  pipeline.py           runs stages 2-4 and writes data/processed/
"""
