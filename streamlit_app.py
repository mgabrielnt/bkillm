"""Simple web chat for the BKI RAG chatbot: `streamlit run streamlit_app.py`.

Safety for public deployment:
- the API key comes only from environment variables / Streamlit secrets and is never shown;
- a daily question cap shared by all users protects the API balance, plus per-session limits;
- questions are length-limited, the model output is rendered as plain Markdown (no HTML);
- internal errors are logged server-side, users only see a generic message;
- optional APP_PASSWORD gate for private test deployments.
"""
from __future__ import annotations

import hmac
import logging
import os
import sys
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

# Streamlit Cloud secrets -> environment, before the package reads its configuration.
try:
    for key, value in st.secrets.items():
        if isinstance(value, (str, int, float)):
            os.environ.setdefault(key, str(value))
except Exception:  # no secrets.toml locally: .env is used instead
    pass

from bki_rag.app.limits import DailyLimiter  # noqa: E402
from bki_rag.core import config as C  # noqa: E402
from bki_rag.generation.answer import RAG  # noqa: E402

log = logging.getLogger("bki_rag.web")
st.set_page_config(page_title="Asisten Informasi BKI", page_icon="⚓", layout="centered")


def friendly_error(exc: Exception) -> str:
    """Tells the app owner what to fix without exposing secrets or stack traces."""
    import openai

    if isinstance(exc, openai.AuthenticationError) or "api_key" in str(exc).lower():
        return ("Layanan belum terkonfigurasi: API key kosong atau ditolak. Pemilik aplikasi: periksa "
                "OPENAI_API_KEY dan OPENAI_BASE_URL di Settings > Secrets.")
    if isinstance(exc, openai.NotFoundError):
        return "Model AI yang diatur tidak tersedia. Pemilik aplikasi: periksa CHAT_MODEL / FAST_MODEL di Secrets."
    if isinstance(exc, (openai.RateLimitError, openai.PermissionDeniedError)) or "budget" in str(exc).lower():
        return "Kuota atau saldo layanan AI sedang habis. Silakan coba lagi nanti."
    if isinstance(exc, openai.APIConnectionError):
        return "Tidak bisa terhubung ke layanan AI. Silakan coba lagi sebentar lagi."
    return "Maaf, terjadi gangguan saat menjawab. Silakan coba lagi sebentar lagi."


@st.cache_resource(show_spinner="Memuat data...")
def load() -> tuple[RAG, DailyLimiter]:
    return RAG(), DailyLimiter(C.USAGE_FILE, C.DAILY_QUESTION_LIMIT)


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


def source_links(sources: list[dict], lang: str) -> str:
    label, page = ("Sources", "p.") if lang == "en" else ("Sumber", "hal.")
    lines = []
    for s in sources:
        title = s["title"].replace("[", "(").replace("]", ")")
        p = s["pages"]
        pages = "" if not p else f" ({page} {p[0]})" if p[0] == p[1] else f" ({page} {p[0]}-{p[1]})"
        lines.append(f"{s['n']}. [{title}]({s['url']}){pages}")
    return f"**{label}:**\n\n" + "\n".join(lines)


def show(msg: dict) -> None:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            st.caption(source_links(msg["sources"], msg.get("lang", "id")))


def main() -> None:
    st.title("Asisten Informasi BKI")
    st.caption("Jawaban disusun otomatis dari situs bki.co.id dan laporan resmi BKI, lengkap dengan sumbernya. "
               "Ini bukan kanal resmi PT Biro Klasifikasi Indonesia; untuk keperluan resmi hubungi BKI langsung.")
    password_gate()
    if not os.environ.get("OPENAI_API_KEY"):
        st.error("Layanan belum terkonfigurasi: OPENAI_API_KEY belum diisi. Pemilik aplikasi: isi di Settings > Secrets.")
        st.stop()
    rag, limiter = load()

    ss = st.session_state
    ss.setdefault("messages", [])
    ss.setdefault("asked", 0)
    ss.setdefault("last_ask", 0.0)

    with st.sidebar:
        if st.button("Percakapan baru", use_container_width=True):
            ss.messages = []
            st.rerun()

    for msg in ss.messages:
        show(msg)

    question = st.chat_input("Tulis pertanyaan tentang BKI...", max_chars=C.MAX_QUESTION_CHARS)
    if not question or not question.strip():
        return
    question = question.strip()

    if ss.asked >= C.SESSION_QUESTION_LIMIT:
        st.warning("Batas pertanyaan untuk sesi ini sudah tercapai. Silakan coba lagi nanti.")
        return
    if time.time() - ss.last_ask < C.MIN_SECONDS_BETWEEN_QUESTIONS:
        st.warning("Mohon tunggu beberapa detik sebelum bertanya lagi.")
        return
    if not limiter.try_consume():
        st.warning("Batas pertanyaan harian layanan ini sudah tercapai. Silakan coba lagi besok.")
        return

    ss.asked += 1
    ss.last_ask = time.time()
    user_msg = {"role": "user", "content": question}
    ss.messages.append(user_msg)
    show(user_msg)

    history = [{"role": m["role"], "content": m["content"]} for m in ss.messages[:-1]][-6:]
    with st.chat_message("assistant"):
        with st.spinner("Mencari jawaban..."):
            try:
                res = rag.answer(question, history)
            except Exception as exc:
                log.exception("answer failed")
                st.error(friendly_error(exc))
                return
    bot_msg = {"role": "assistant", "content": res["answer"], "sources": res["sources"],
               "lang": res["query"].get("lang", "id")}
    ss.messages.append(bot_msg)
    st.rerun()


main()
