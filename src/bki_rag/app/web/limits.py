"""Usage guards for the public web app (they protect the API balance).

  * DailyLimiter   a daily question cap shared by all visitors, stored in data/usage/ (resets on restart
                   of a cloud server, so also set a spending limit at the API provider).
  * session_block  per-visitor limits: questions per session and minimum seconds between questions.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import date
from pathlib import Path

from ...core import config as C


# Menghitung pertanyaan per hari di file JSON kecil; aman dipakai banyak thread dalam satu server.
class DailyLimiter:
    # Izinkan maksimal `limit` pertanyaan per hari, dihitung di file JSON `path`.
    def __init__(self, path: Path, limit: int):
        self.path, self.limit = path, limit
        self._lock = threading.Lock()

    # Isi file penghitung ({} jika file belum ada atau rusak).
    def _read(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    # Jumlah pertanyaan yang sudah diajukan hari ini.
    def used_today(self) -> int:
        return int(self._read().get(date.today().isoformat(), 0))

    # Hitung satu pertanyaan; False jika batas hari ini sudah tercapai.
    def try_consume(self) -> bool:
        with self._lock:
            today = date.today().isoformat()
            used = int(self._read().get(today, 0))
            if used >= self.limit:
                return False
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({today: used + 1}), encoding="utf-8")
            return True


# Pesan peringatan jika pengunjung harus menunggu atau berhenti; None jika boleh bertanya.
def session_block(asked: int, last_ask: float) -> str | None:
    if asked >= C.SESSION_QUESTION_LIMIT:
        return "Batas pertanyaan untuk sesi ini sudah tercapai. Silakan coba lagi nanti."
    if time.time() - last_ask < C.MIN_SECONDS_BETWEEN_QUESTIONS:
        return "Mohon tunggu beberapa detik sebelum bertanya lagi."
    return None
