"""The <sources> block given to the chat model.

Each source carries a "status" so the model knows how current it is: live website pages describe BKI
today, dated items (news) their publication date, and reports the year they cover.
"""
from __future__ import annotations

from datetime import datetime
from html import escape

from ..core import config as C
from .citations import display_title

REPORT_TYPES = {"annual_report", "sustainability_report"}


# Tanggal crawl terakhir (waktu file manifest), menunjukkan umur data halaman situs.
def _crawl_date() -> str:
    try:
        return datetime.fromtimestamp(C.MANIFEST.stat().st_mtime).strftime("%Y-%m-%d")
    except OSError:
        return "unknown"


# Seberapa baru sebuah sumber: tahun laporan, tanggal terbit, atau halaman situs aktif.
def _status(chunk: dict, crawled: str) -> str:
    if chunk["doc_type"] in REPORT_TYPES:
        return f"report covering year {(chunk.get('published_at') or '')[:4] or 'unknown'}"
    if chunk.get("published_at"):
        return f"dated item published {chunk['published_at'][:10]}"
    return f"current live website page (crawled {crawled})"


# Susun sumber sebagai XML untuk model; konteks hasil contextual retrieval dipisah dari isi chunk.
def build_context(chunks: list[dict]) -> str:
    crawled = _crawl_date()
    parts = []
    for i, c in enumerate(chunks, 1):
        pages = f' pages="{c["page_from"]}-{c["page_to"]}"' if c.get("page_from") else ""
        ctx = f"<context>{escape(c['context'])}</context>\n" if c.get("context") else ""
        parts.append(f'<source id="{i}" title="{escape(display_title(c))}" url="{c["url"]}" '
                     f'type="{c["doc_type"]}" status="{_status(c, crawled)}"{pages}>\n'
                     f'{ctx}<content>\n{c["text"]}\n</content>\n</source>')
    return "\n\n".join(parts)
