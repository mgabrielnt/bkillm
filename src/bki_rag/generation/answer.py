"""The RAG pipeline for one question.

  1. Restricted topic (rules & regulations)?  -> reply with the login link only (no search, no model call).
  2. Otherwise: retrieve chunks -> ask the chat model -> answer with citations [1]..[k] and a matching
     source list.
"""
from __future__ import annotations

import time

from ..core import config as C
from ..core.llm import chat
from ..prompts import ANSWER_SYSTEM_PROMPT, ANSWER_USER_PROMPT
from ..retrieval.query import detect_lang
from ..retrieval.restricted import RestrictedPage, match_restricted, restricted_reply
from ..retrieval.retriever import RetrievalConfig, Retriever
from .citations import renumber_citations
from .sources import build_context

LANG_NAMES = {"id": "Indonesian", "en": "English"}
HISTORY_TURNS = 6  # pesan riwayat chat terakhir yang ikut dikirim ke model


# Bentuk hasil yang sama untuk semua jalur: jawaban, sumber, chunk, info pertanyaan, dan waktu proses.
def _result(answer: str, sources: list[dict], chunks: list[dict], query: dict, ranking: list[dict],
            t_start: float, t_retrieved: float) -> dict:
    return {"answer": answer, "sources": sources, "chunks": chunks, "query": query, "ranking": ranking,
            "timing": {"retrieval_s": round(t_retrieved - t_start, 2), "total_s": round(time.time() - t_start, 2)}}


# Pesan untuk model jawaban: aturan (system), riwayat chat singkat, lalu sumber + pertanyaan.
def _messages(question: str, query: dict, chunks: list[dict], history: list[dict] | None) -> list[dict]:
    standalone = query.get("standalone", question)
    user = ANSWER_USER_PROMPT.format(
        sources=build_context(chunks), question=standalone,
        original=f"\n(Original wording: {question})" if standalone != question else "",
        lang=LANG_NAMES.get(query.get("lang"), "same as the question"))
    past = [{"role": m["role"], "content": m["content"]} for m in (history or [])[-HISTORY_TURNS:]]
    return [{"role": "system", "content": ANSWER_SYSTEM_PROMPT}, *past, {"role": "user", "content": user}]


# Pipeline RAG untuk satu pertanyaan: cari sumber, tanya model, kembalikan jawaban + sumber.
class RAG:
    # Pakai retriever yang diberikan (default: data/index) dan konfigurasi pencariannya.
    def __init__(self, retriever: Retriever | None = None, cfg: RetrievalConfig = RetrievalConfig()):
        self.retriever = retriever or Retriever()
        self.cfg = cfg

    # Mengembalikan {"answer", "sources", "chunks", "query", "ranking", "timing"}. "answer" memakai sitasi
    # [1]..[k] dan "sources" berisi nomor yang sama persis.
    def answer(self, question: str, history: list[dict] | None = None) -> dict:
        t0 = time.time()
        page = match_restricted(question)
        if page:
            return self._restricted(question, page, t0)
        found = self.retriever.search(question, history, self.cfg)
        t1 = time.time()
        chunks, query = found["chunks"], found["query"]
        reply = chat(_messages(question, query, chunks, history), model=C.CHAT_MODEL, reasoning=C.CHAT_REASONING)
        text, sources = renumber_citations(reply, chunks)
        return _result(text, sources, chunks, query, found["ranking"], t0, t1)

    # Topik di balik login: hanya link login, tanpa pencarian dan tanpa memanggil model.
    @staticmethod
    def _restricted(question: str, page: RestrictedPage, t0: float) -> dict:
        lang = detect_lang(question)
        query = {"standalone": question, "lang": lang, "restricted": page.url}
        return _result(restricted_reply(page, lang), [], [], query, [], t0, time.time())
