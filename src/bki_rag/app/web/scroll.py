"""Auto-scroll the chat to the newest message (Streamlit does not do this by itself)."""
from __future__ import annotations

import streamlit.components.v1 as components

# Skrip kecil di iframe tak terlihat: cari kontainer scroll Streamlit di halaman induk, lalu gulir ke dasar.
_SCRIPT = """
<script>
const doc = window.parent.document;
const box = doc.querySelector('[data-testid="stMain"]') || doc.querySelector('section.main');
if (box) { box.scrollTo({top: box.scrollHeight, behavior: 'smooth'}); }
</script>
"""


# Gulir halaman ke pesan paling bawah (dipanggil saat pertanyaan baru dikirim dan setelah jawaban selesai).
def scroll_to_bottom() -> None:
    components.html(_SCRIPT, height=0)
