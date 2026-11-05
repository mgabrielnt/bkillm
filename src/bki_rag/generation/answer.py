"""The RAG pipeline for one question.

  1. Restricted topic (rules & regulations)?  -> reply with the login link only (no search, no model call).
  2. Otherwise: retrieve chunks -> ask the chat model -> answer with citations [1]..[k] and a matching
     source list.
"""
from __future__ import annotations

import re
import time
from typing import Callable

from ..core import config as C
from ..core.llm import chat, chat_stream
from ..prompts import ANSWER_SYSTEM_PROMPT, ANSWER_USER_PROMPT
from ..retrieval.query import detect_lang
from ..retrieval.restricted import RestrictedPage, match_restricted, restricted_reply
from ..retrieval.retriever import Retriever
from .citations import renumber_citations
from .sources import build_context

LANG_NAMES = {"id": "Indonesian", "en": "English"}
HISTORY_TURNS = 6  # pesan riwayat chat terakhir yang ikut dikirim ke model
# Tanda penolakan di awal jawaban (lihat aturan 3 di prompt jawaban).
REFUSAL = re.compile(r"^(maaf|sorry)|tidak (ditemukan|ada|tersedia|disebut|mencantumkan)|no specific|"
                     r"not (found|available|mentioned|stated|provided|specified)|"
                     r"(do|does) not (include|contain|provide|mention|state|specify)", re.I)
HOLD_CHARS = 60  # huruf pertama yang ditahan sebelum tampil, supaya penolakan bisa dicek ulang


# Bentuk hasil yang sama untuk semua jalur: jawaban, sumber, chunk, info pertanyaan, dan waktu proses.
def _result(answer: str, sources: list[dict], chunks: list[dict], query: dict, ranking: list[dict],
            timing: dict) -> dict:
    return {"answer": answer, "sources": sources, "chunks": chunks, "query": query, "ranking": ranking,
            "timing": timing}


# Tanya model satu kali. Mengembalikan (teks, waktu teks pertama), atau None jika drop_refusal aktif dan
# jawabannya penolakan. Beberapa huruf pertama ditahan agar penolakan itu tidak sempat tampil di layar.
def _ask_model(messages: list[dict], reasoning: str, on_text: Callable[[str], None] | None,
               drop_refusal: bool) -> tuple[str, float] | None:
    args = {"reasoning": reasoning, "verbosity": C.ANSWER_VERBOSITY}
    deltas = chat_stream(messages, **args) if C.STREAM_ANSWER else [chat(messages, **args)]
    show = on_text or (lambda _: None)
    text, first = "", 0.0
    held = True
    for delta in deltas:
        text += delta
        if not held:
            show(delta)
        elif len(text) >= HOLD_CHARS:
            if drop_refusal and REFUSAL.search(text):
                return None
            held = False
            first = time.time()
            show(text)
    if held:
        if drop_refusal and REFUSAL.search(text):
            return None
        first = time.time()
        show(text)
    return text, first


# Jawaban cepat dulu; penolakan dicek ulang lebih teliti karena model cepat bisa melewatkan isi tabel.
def _reply(messages: list[dict], on_text: Callable[[str], None] | None) -> tuple[str, float]:
    retry = C.RETRY_REASONING if C.RETRY_REASONING != C.ANSWER_REASONING else ""
    return (_ask_model(messages, C.ANSWER_REASONING, on_text, bool(retry))
            or _ask_model(messages, retry, on_text, False))


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
    # Pakai retriever yang diberikan (default: pencarian di data/index).
    def __init__(self, retriever: Retriever | None = None):
        self.retriever = retriever or Retriever()

    # Mengembalikan {"answer", "sources", "chunks", "query", "ranking", "timing"}. "answer" memakai sitasi
    # [1]..[k] dan "sources" berisi nomor yang sama persis. on_text menerima potongan jawaban selagi ditulis.
    def answer(self, question: str, history: list[dict] | None = None,
               on_text: Callable[[str], None] | None = None) -> dict:
        t0 = time.time()
        page = match_restricted(question)
        if page:
            return self._restricted(question, page, t0)
        found = self.retriever.search(question, history)
        t1 = time.time()
        chunks, query = found["chunks"], found["query"]
        reply, t_first = _reply(_messages(question, query, chunks, history), on_text)
        t2 = time.time()
        text, sources = renumber_citations(reply, chunks)
        timing = {**found["timing"], "retrieval_s": round(t1 - t0, 3), "first_text_s": round(t_first - t0, 3),
                  "answer_s": round(t2 - t1, 3), "total_s": round(time.time() - t0, 3)}
        return _result(text, sources, chunks, query, found["ranking"], timing)

    # Topik di balik login: hanya link login, tanpa pencarian dan tanpa memanggil model.
    @staticmethod
    def _restricted(question: str, page: RestrictedPage, t0: float) -> dict:
        lang = detect_lang(question)
        query = {"standalone": question, "lang": lang, "restricted": page.url}
        timing = {"retrieval_s": 0.0, "total_s": round(time.time() - t0, 3)}
        return _result(restricted_reply(page, lang), [], [], query, [], timing)
