"""Penghitung token API dan biaya (dipakai evaluasi untuk menghitung biaya per pertanyaan)."""
from __future__ import annotations

import threading

from . import config as C

_USAGE = {"llm_in": 0, "llm_out": 0, "embed": 0}  # token terpakai sejak program mulai
_USAGE_LOCK = threading.Lock()


# Tambahkan jumlah token ke penghitung pemakaian.
def track(key: str, tokens: int | None) -> None:
    with _USAGE_LOCK:
        _USAGE[key] += tokens or 0


# Salinan penghitung token: {"llm_in", "llm_out", "embed"}.
def usage() -> dict:
    with _USAGE_LOCK:
        return dict(_USAGE)


# Biaya dalam USD dari selisih dua salinan penghitung token (harga per 1 juta token di config).
def cost_usd(before: dict, after: dict) -> float:
    return sum((after[k] - before[k]) * C.PRICE_PER_1M_TOKENS[k] / 1e6 for k in _USAGE)
