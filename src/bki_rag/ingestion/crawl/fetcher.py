"""Polite HTTP client used by every crawler module, plus small shared helpers.

The site sits behind a WAF: we identify honestly (config.USER_AGENT), wait REQUEST_DELAY_S between
requests and retry with backoff on 5xx or WAF rejections. We never try to evade the WAF.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from ...core import config as C

REJECTED_MARKER = b"The requested URL was rejected"


# GET dengan jeda tetap antar request dan backoff bertingkat saat gagal.
class Fetcher:
    # Client HTTP dengan User-Agent jujur dan jeda antar request.
    def __init__(self, delay: float = C.REQUEST_DELAY_S):
        self.delay = delay
        self._last = 0.0
        self.client = httpx.Client(headers={"User-Agent": C.USER_AGENT}, timeout=120, follow_redirects=True)

    # GET sebuah URL dengan sopan; ulangi jika error jaringan, 5xx, atau ditolak WAF.
    def get(self, url: str, retries: int = 4) -> httpx.Response:
        resp = None
        for attempt in range(retries + 1):
            wait = self.delay - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            try:
                resp = self.client.get(url)
            except httpx.HTTPError:
                resp = None
            self._last = time.time()
            if resp is not None and resp.status_code < 500 and not is_rejected(resp.content):
                return resp
            if attempt < retries:
                time.sleep(2 ** attempt * 2)
        if resp is None:
            raise RuntimeError(f"network error: {url}")
        return resp


# True jika WAF mengirim halaman 'Request Rejected' alih-alih konten.
def is_rejected(content: bytes) -> bool:
    return REJECTED_MARKER in content[:400]


# Nama file yang aman dari path sebuah URL.
def slug(url: str) -> str:
    path = urlparse(url).path.strip("/") or "home"
    return re.sub(r"[^a-zA-Z0-9]+", "_", path)[:150]


# Waktu UTC sekarang dalam format ISO, untuk manifest.
def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
