"""User-facing error messages: tell the app owner what to fix without exposing secrets or stack traces."""
from __future__ import annotations

import openai

MISSING_KEY = ("Layanan belum terkonfigurasi: OPENAI_API_KEY belum diisi. "
               "Pemilik aplikasi: isi di Settings > Secrets.")


def friendly_error(exc: Exception) -> str:
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
