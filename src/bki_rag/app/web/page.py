"""The chat page: history, question box, usage limits, answer with sources."""
from __future__ import annotations

import logging
import os
import time

import streamlit as st

from ...core import config as C
from ...generation.answer import RAG
from .errors import MISSING_KEY, friendly_error
from .limits import DailyLimiter, session_block
from .views import DISCLAIMER, TITLE, password_gate, show_message

log = logging.getLogger("bki_rag.web")


# Dimuat sekali per server dan dipakai bersama semua pengunjung (index hanya dibaca).
@st.cache_resource(show_spinner="Memuat data...")
def _load() -> tuple[RAG, DailyLimiter]:
    return RAG(), DailyLimiter(C.USAGE_FILE, C.DAILY_QUESTION_LIMIT)


# Tampilkan pertanyaan, jawab, lalu simpan keduanya di riwayat sesi.
def _ask(rag: RAG, question: str) -> None:
    ss = st.session_state
    ss.asked += 1
    ss.last_ask = time.time()
    history = [{"role": m["role"], "content": m["content"]} for m in ss.messages][-6:]
    ss.messages.append({"role": "user", "content": question})
    show_message(ss.messages[-1])
    with st.chat_message("assistant"), st.spinner("Mencari jawaban..."):
        try:
            res = rag.answer(question, history)
        except Exception as exc:
            log.exception("answer failed")
            st.error(friendly_error(exc))
            return
    ss.messages.append({"role": "assistant", "content": res["answer"], "sources": res["sources"],
                        "lang": res["query"].get("lang", "id")})
    st.rerun()


# Tampilkan halaman chat: judul, kata sandi, riwayat, kotak pertanyaan, dan batas pemakaian.
def main() -> None:
    st.title(TITLE)
    st.caption(DISCLAIMER)
    password_gate()
    if not os.environ.get("OPENAI_API_KEY"):
        st.error(MISSING_KEY)
        st.stop()
    rag, limiter = _load()

    ss = st.session_state
    ss.setdefault("messages", [])
    ss.setdefault("asked", 0)
    ss.setdefault("last_ask", 0.0)
    with st.sidebar:
        if st.button("Percakapan baru", use_container_width=True):
            ss.messages = []
            st.rerun()
    for msg in ss.messages:
        show_message(msg)

    question = (st.chat_input("Tulis pertanyaan tentang BKI...", max_chars=C.MAX_QUESTION_CHARS) or "").strip()
    if not question:
        return
    warning = session_block(ss.asked, ss.last_ask)
    if warning is None and not limiter.try_consume():
        warning = "Batas pertanyaan harian layanan ini sudah tercapai. Silakan coba lagi besok."
    if warning:
        st.warning(warning)
        return
    _ask(rag, question)
