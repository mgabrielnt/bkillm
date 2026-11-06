"""Ask the chat model for the answer text: streaming, plus a careful second try when it refuses.

The fast model (`ANSWER_REASONING`) answers first. If that answer is a refusal ("not found"), it is held back
and asked again with `RETRY_REASONING`, because the fast model sometimes misses figures inside tables.
"""
from __future__ import annotations

import re
import time
from typing import Callable

from ..core import config as C
from ..core.llm import chat, chat_stream

# Tanda penolakan di awal jawaban (lihat aturan 3 di prompt jawaban).
REFUSAL = re.compile(r"^(maaf|sorry)|tidak (ditemukan|ada|tersedia|disebut|mencantumkan)|no specific|"
                     r"not (found|available|mentioned|stated|provided|specified)|"
                     r"(do|does) not (include|contain|provide|mention|state|specify)", re.I)
HOLD_CHARS = 60  # huruf pertama yang ditahan sebelum tampil, supaya penolakan bisa dicek ulang


# Tanya model satu kali. Mengembalikan (teks, waktu teks pertama), atau None jika drop_refusal aktif dan
# jawabannya penolakan. Beberapa huruf pertama ditahan agar penolakan itu tidak sempat tampil di layar.
def ask_model(messages: list[dict], reasoning: str, on_text: Callable[[str], None] | None,
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
def reply(messages: list[dict], on_text: Callable[[str], None] | None) -> tuple[str, float]:
    retry = C.RETRY_REASONING if C.RETRY_REASONING != C.ANSWER_REASONING else ""
    return (ask_model(messages, C.ANSWER_REASONING, on_text, bool(retry))
            or ask_model(messages, retry, on_text, False))
