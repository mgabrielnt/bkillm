"""Usage guard for the public web app: a daily question cap shared by all users (protects the API balance)."""
from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path


class DailyLimiter:
    """Counts questions per calendar day in a small JSON file. Thread-safe within one server process."""

    def __init__(self, path: Path, limit: int):
        self.path, self.limit = path, limit
        self._lock = threading.Lock()

    def _read(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def used_today(self) -> int:
        return int(self._read().get(date.today().isoformat(), 0))

    def try_consume(self) -> bool:
        with self._lock:
            today = date.today().isoformat()
            used = int(self._read().get(today, 0))
            if used >= self.limit:
                return False
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({today: used + 1}), encoding="utf-8")
            return True
