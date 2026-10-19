"""Small Streamlit building blocks: password gate, chat bubbles and the source list under an answer."""
from __future__ import annotations

import hmac

import streamlit as st

from ...core import config as C

TITLE = "Asisten Informasi BKI"
DISCLAIMER = ("Jawaban disusun otomatis dari situs bki.co.id dan laporan resmi BKI, lengkap dengan sumbernya. "
              "Ini bukan kanal resmi PT Biro Klasifikasi Indonesia; untuk keperluan resmi hubungi BKI langsung.")


def password_gate() -> None:
    """Stops the page until the right APP_PASSWORD is entered (no-op when no password is set)."""
    if not C.APP_PASSWORD or st.session_state.get("authed"):
        return
    pw = st.text_input("Kata sandi", type="password")
    if pw and hmac.compare_digest(pw, C.APP_PASSWORD):
        st.session_state.authed = True
        st.rerun()
    elif pw:
        st.error("Kata sandi salah.")
    st.stop()


def source_links(sources: list[dict], lang: str) -> str:
    """Links labelled [n] exactly like the citations in the answer.

    Written as "[n] link" lines, not a Markdown numbered list, because Markdown would renumber the list.
    """
    label, page = ("Sources", "p.") if lang == "en" else ("Sumber", "hal.")
    lines = []
    for s in sources:
        title = s["title"].replace("[", "(").replace("]", ")")
        p = s["pages"]
        pages = "" if not p else f" ({page} {p[0]})" if p[0] == p[1] else f" ({page} {p[0]}-{p[1]})"
        lines.append(f"\\[{s['n']}\\] [{title}]({s['url']}){pages}")
    return f"**{label}:**  \n" + "  \n".join(lines)


def show_message(msg: dict) -> None:
    """One chat bubble; model output is plain Markdown (Streamlit does not render HTML here)."""
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            st.caption(source_links(msg["sources"], msg.get("lang", "id")))
