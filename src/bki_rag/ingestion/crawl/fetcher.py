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


class Fetcher:
    """GET with a fixed delay between requests and exponential backoff on failures."""

    def __init__(self, delay: float = C.REQUEST_DELAY_S):
        """HTTP client with the honest User-Agent and the delay between requests."""
        self.delay = delay
        self._last = 0.0
        self.client = httpx.Client(headers={"User-Agent": C.USER_AGENT}, timeout=120, follow_redirects=True)

    def get(self, url: str, retries: int = 4) -> httpx.Response:
        """GET a URL politely; retries on network errors, 5xx and WAF rejections."""
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


def is_rejected(content: bytes) -> bool:
    """True when the WAF answered with its 'Request Rejected' page instead of content."""
    return REJECTED_MARKER in content[:400]


def slug(url: str) -> str:
    """File-system friendly name for a URL path."""
    path = urlparse(url).path.strip("/") or "home"
    return re.sub(r"[^a-zA-Z0-9]+", "_", path)[:150]


def now() -> str:
    """Current UTC time as ISO text, for the manifest."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
