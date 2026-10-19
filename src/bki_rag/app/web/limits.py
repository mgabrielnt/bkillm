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


class DailyLimiter:
    """Counts questions per calendar day in a small JSON file. Thread-safe within one server process."""

    def __init__(self, path: Path, limit: int):
        """Allow at most `limit` questions per day, counted in the JSON file at `path`."""
        self.path, self.limit = path, limit
        self._lock = threading.Lock()

    def _read(self) -> dict:
        """Counter file contents ({} when missing or unreadable)."""
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def used_today(self) -> int:
        """Number of questions already asked today."""
        return int(self._read().get(date.today().isoformat(), 0))

    def try_consume(self) -> bool:
        """Count one question; False when today's limit is already reached."""
        with self._lock:
            today = date.today().isoformat()
            used = int(self._read().get(today, 0))
            if used >= self.limit:
                return False
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({today: used + 1}), encoding="utf-8")
            return True


def session_block(asked: int, last_ask: float) -> str | None:
    """Warning to show when this visitor must wait or stop, otherwise None."""
    if asked >= C.SESSION_QUESTION_LIMIT:
        return "Batas pertanyaan untuk sesi ini sudah tercapai. Silakan coba lagi nanti."
    if time.time() - last_ask < C.MIN_SECONDS_BETWEEN_QUESTIONS:
        return "Mohon tunggu beberapa detik sebelum bertanya lagi."
    return None
