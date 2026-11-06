"""Stop button support: keep the partial answer when the user interrupts a running answer."""
from __future__ import annotations

import streamlit as st

from ...generation.citations import hide_citations


# Klik tombol (atau pertanyaan baru) membatalkan proses menjawab di tengah jalan. Teks yang sudah tampil
# disimpan di riwayat dengan tanda "Dihentikan", supaya tidak hilang.
def commit_stopped() -> None:
    parts = st.session_state.pop("pending", None)
    if parts is None:
        return
    text = hide_citations("".join(parts)).strip()
    note = "_(Dihentikan)_"
    st.session_state.messages.append({"role": "assistant", "content": f"{text}\n\n{note}" if text else note})
