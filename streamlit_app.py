"""Entry point of the web chat: `streamlit run streamlit_app.py` (also used by Streamlit Cloud).

Only bootstrapping happens here; the page itself lives in src/bki_rag/app/web/.
Safety for public deployment: the API key comes only from env / Streamlit Secrets and is never shown;
daily and per-session question limits protect the API balance; answers are rendered without HTML;
errors are logged server-side; APP_PASSWORD optionally makes the app private.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

# Secrets Streamlit Cloud -> environment variable, sebelum paket membaca konfigurasinya.
try:
    for key, value in st.secrets.items():
        if isinstance(value, (str, int, float)):
            os.environ.setdefault(key, str(value))
except Exception:  # tanpa secrets.toml di lokal: pakai .env
    pass

st.set_page_config(page_title="Asisten Informasi BKI", page_icon="⚓", layout="centered")

from bki_rag.app.web.page import main  # noqa: E402

main()
