"""Stage 6b - grounded answer generation with citations."""
from __future__ import annotations

import re
import time
from datetime import datetime
from html import escape

from ..core import config as C
from ..core.llm import chat
from ..prompts import ANSWER_SYSTEM_PROMPT, ANSWER_USER_PROMPT
from ..retrieval.retriever import RetrievalConfig, Retriever

LANG_NAMES = {"id": "Indonesian", "en": "English"}
REPORT_TYPES = {"annual_report", "sustainability_report"}


def _crawl_date() -> str:
    try:
        return datetime.fromtimestamp(C.MANIFEST.stat().st_mtime).strftime("%Y-%m-%d")
    except OSError:
        return "unknown"


def _status(c: dict, crawled: str) -> str:
    """Tells the model how current a source is: live pages describe today, reports describe their year."""
    if c["doc_type"] in REPORT_TYPES:
        return f"report covering year {(c.get('published_at') or '')[:4] or 'unknown'}"
    if c.get("published_at"):
        return f"dated item published {c['published_at'][:10]}"
    return f"current live website page (crawled {crawled})"


def build_context(chunks: list[dict]) -> str:
    """Sources as XML; the contextual-retrieval description is kept separate from the chunk content."""
    crawled = _crawl_date()
    parts = []
    for i, c in enumerate(chunks, 1):
        pages = f' pages="{c["page_from"]}-{c["page_to"]}"' if c.get("page_from") else ""
        ctx = f"<context>{escape(c['context'])}</context>\n" if c.get("context") else ""
        parts.append(f'<source id="{i}" title="{escape(c["title"])}" url="{c["url"]}" type="{c["doc_type"]}" '
                     f'status="{_status(c, crawled)}"{pages}>\n{ctx}<content>\n{c["text"]}\n</content>\n</source>')
    return "\n\n".join(parts)


_CITATION = re.compile(r"\[((?:(?:sources?|sumber)\s*)?\d+(?:\s*[,;]\s*(?:(?:sources?|sumber)\s*)?\d+)*)\]", re.I)


def normalize_citations(text: str) -> str:
    """Small models sometimes write [source 5; source 3] or [1, 2]; rewrite those as [5][3] / [1][2]."""
    return _CITATION.sub(lambda m: "".join(f"[{n}]" for n in re.findall(r"\d+", m.group(1))), text)


def cited_sources(text: str, chunks: list[dict]) -> list[dict]:
    """Sources actually cited as [n]; several chunks of the same page collapse into one."""
    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", text) if 0 < int(n) <= len(chunks)})
    sources, seen = [], set()
    for n in cited:
        c = chunks[n - 1]
        pages = (c["page_from"], c["page_to"]) if c.get("page_from") else None
        if (c["url"], pages) not in seen:
            seen.add((c["url"], pages))
            sources.append({"n": n, "title": c["title"], "url": c["url"], "pages": pages})
    return sources


class RAG:
    def __init__(self, retriever: Retriever | None = None, cfg: RetrievalConfig = RetrievalConfig()):
        self.retriever = retriever or Retriever()
        self.cfg = cfg

    def answer(self, question: str, history: list[dict] | None = None) -> dict:
        t0 = time.time()
        found = self.retriever.search(question, history, self.cfg)
        t1 = time.time()
        chunks, q = found["chunks"], found["query"]
        standalone = q.get("standalone", question)
        user = ANSWER_USER_PROMPT.format(
            sources=build_context(chunks), question=standalone,
            original=f"\n(Original wording: {question})" if standalone != question else "",
            lang=LANG_NAMES.get(q.get("lang"), "same as the question"))
        messages = [{"role": "system", "content": ANSWER_SYSTEM_PROMPT}]
        messages += [{"role": m["role"], "content": m["content"]} for m in (history or [])[-6:]]
        messages.append({"role": "user", "content": user})
        text = normalize_citations(chat(messages, model=C.CHAT_MODEL, reasoning=C.CHAT_REASONING))
        return {"answer": text, "sources": cited_sources(text, chunks), "chunks": chunks, "query": q,
                "ranking": found["ranking"],
                "timing": {"retrieval_s": round(t1 - t0, 2), "total_s": round(time.time() - t0, 2)}}
