"""The RAG pipeline for one question: retrieve -> ask the chat model -> answer with a matching source list."""
from __future__ import annotations

import time

from ..core import config as C
from ..core.llm import chat
from ..prompts import ANSWER_SYSTEM_PROMPT, ANSWER_USER_PROMPT
from ..retrieval.retriever import RetrievalConfig, Retriever
from .citations import renumber_citations
from .sources import build_context

LANG_NAMES = {"id": "Indonesian", "en": "English"}


class RAG:
    def __init__(self, retriever: Retriever | None = None, cfg: RetrievalConfig = RetrievalConfig()):
        self.retriever = retriever or Retriever()
        self.cfg = cfg

    def answer(self, question: str, history: list[dict] | None = None) -> dict:
        """Returns {"answer", "sources", "chunks", "query", "ranking", "timing"}.

        "answer" cites [1]..[k] and "sources" lists exactly those numbers.
        """
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
        text, sources = renumber_citations(chat(messages, model=C.CHAT_MODEL, reasoning=C.CHAT_REASONING), chunks)
        return {"answer": text, "sources": sources, "chunks": chunks, "query": q, "ranking": found["ranking"],
                "timing": {"retrieval_s": round(t1 - t0, 2), "total_s": round(time.time() - t0, 2)}}
