"""Small Streamlit building blocks: password gate, chat bubbles and the source list under an answer."""
from __future__ import annotations

import hmac

import streamlit as st

from ...core import config as C

TITLE = "Asisten Informasi BKI"
DISCLAIMER = ("Jawaban disusun otomatis dari situs bki.co.id dan laporan resmi BKI, lengkap dengan sumbernya. "
              "Ini bukan kanal resmi PT Biro Klasifikasi Indonesia; untuk keperluan resmi hubungi BKI langsung.")


# Hentikan halaman sampai APP_PASSWORD yang benar dimasukkan (tidak berbuat apa-apa jika kata sandi tidak
# diatur).
def password_gate() -> None:
    if not C.APP_PASSWORD or st.session_state.get("authed"):
        return
    pw = st.text_input("Kata sandi", type="password")
    if pw and hmac.compare_digest(pw, C.APP_PASSWORD):
        st.session_state.authed = True
        st.rerun()
    elif pw:
        st.error("Kata sandi salah.")
    st.stop()


# Link sumber berlabel [n], sama persis dengan sitasi di jawaban. Ditulis sebagai baris "[n] link", bukan
# daftar bernomor Markdown, karena Markdown akan menomori ulang daftarnya.
def source_links(sources: list[dict], lang: str) -> str:
    label, page = ("Sources", "p.") if lang == "en" else ("Sumber", "hal.")
    lines = []
    for s in sources:
        title = s["title"].replace("[", "(").replace("]", ")")
        p = s["pages"]
        pages = "" if not p else f" ({page} {p[0]})" if p[0] == p[1] else f" ({page} {p[0]}-{p[1]})"
        lines.append(f"\\[{s['n']}\\] [{title}]({s['url']}){pages}")
    return f"**{label}:**  \n" + "  \n".join(lines)


# Satu gelembung chat; jawaban model ditampilkan sebagai Markdown biasa (tanpa HTML).
def show_message(msg: dict) -> None:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            st.caption(source_links(msg["sources"], msg.get("lang", "id")))
