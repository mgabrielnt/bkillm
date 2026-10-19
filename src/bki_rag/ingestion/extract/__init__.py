"""Stage 2 - turn raw files into Markdown documents with metadata.

Modules:
  rsc.py       decode the Next.js React Server Components payload; find the i18n dictionary
  rsc_text.py  visible text of a page's element tree
  i18n.py      render a dictionary namespace as Markdown (label first, then its text)
  urls.py      namespace -> page URL for citations; URL -> document type
  pages.py     documents for the static pages (English + Indonesian)
  tiptap.py    CMS rich text (TipTap JSON, Strapi blocks) -> Markdown
  cms.py       documents for news, articles, events, ESG pages, job postings
  pdf.py       documents for report PDFs, one section per page
"""
from .cms import cms_docs
from .pages import page_docs
from .pdf import pdf_docs

__all__ = ["cms_docs", "page_docs", "pdf_docs"]
