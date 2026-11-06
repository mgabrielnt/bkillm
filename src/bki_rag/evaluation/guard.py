"""Keep the evaluation alive when the API fails: errors are recorded per question instead of crashing the run."""
from __future__ import annotations

import threading
from typing import Callable

import openai


# Pesan singkat untuk error API: apa yang terjadi dan apa yang harus dilakukan.
def api_error_msg(exc: Exception) -> str:
    text = str(exc).lower()
    if "budget" in text or "quota" in text or "insufficient" in text:
        return "Saldo/budget API habis. Naikkan budget API key (atau tunggu reset), lalu jalankan lagi."
    if isinstance(exc, openai.AuthenticationError):
        return "API key ditolak. Periksa OPENAI_API_KEY di .env."
    if isinstance(exc, openai.APIConnectionError):
        return "Tidak bisa terhubung ke layanan AI. Periksa internet / OPENAI_BASE_URL."
    return f"{type(exc).__name__}: {str(exc)[:200]}"


# Pembungkus panggilan API per soal: error dicatat sebagai {"error": pesan} agar evaluasi tidak berhenti,
# dan begitu budget habis / API key ditolak, soal berikutnya langsung dilewati tanpa memanggil API.
class Guard:
    # stop: tanda budget habis; reason: pesan penyebabnya.
    def __init__(self) -> None:
        self.stop = threading.Event()
        self.reason = ""

    # Jalankan fn(*args); jika API error, kembalikan {"error": pesan} alih-alih melempar exception.
    def __call__(self, fn: Callable[..., dict], *args) -> dict:
        if self.stop.is_set():
            return {"error": self.reason}
        try:
            return fn(*args)
        except openai.APIError as exc:
            msg = api_error_msg(exc)
            if "budget" in msg.lower() or isinstance(exc, openai.AuthenticationError):
                self.reason = msg
                self.stop.set()
            return {"error": msg}
