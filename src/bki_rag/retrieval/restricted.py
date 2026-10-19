"""Topics that live behind BKI's login: answer with the login link only, without searching anything.

Every question that mentions rules or regulations (in English or Indonesian, including suffixed forms such
as "peraturannya" or "regulasinya") goes straight to the BKI Rules & Regulations page. Matching is a plain
keyword check on the question text: no embedding, no retrieval and no model call, so it costs nothing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


# Satu halaman yang butuh login: nama, link, dan pola kata kunci yang mengarah ke halaman itu.
@dataclass(frozen=True)
class RestrictedPage:
    name: str
    url: str
    pattern: re.Pattern


RULES_PAGE = RestrictedPage(
    name="BKI Rules & Regulations",
    url="https://www.bki.co.id/research/rnd/bki-rules-regulations",
    pattern=re.compile(
        r"\b(rules?|regulat\w*"                      # rule, rules, regulation(s), regulatory
        r"|aturan\w*|peraturan\w*|regulasi\w*"       # aturan, peraturan, regulasi (+ akhiran -nya, -an)
        r"|ketentuan\w*|pedoman\w*|guidelines?|guidance"
        r"|standar\s+teknis|technical\s+standards?)\b",
        re.IGNORECASE,
    ),
)
RESTRICTED_PAGES = (RULES_PAGE,)

REPLIES = {
    "id": "Informasi tentang {name} hanya tersedia bagi pengguna terdaftar. "
          "Silakan login untuk mengaksesnya di: {url}",
    "en": "Information about {name} is only available to registered users. "
          "Please log in to access it at: {url}",
}


# Halaman login yang dibahas pertanyaan ini, atau None jika pertanyaan biasa.
def match_restricted(question: str) -> RestrictedPage | None:
    return next((page for page in RESTRICTED_PAGES if page.pattern.search(question)), None)


# Balasan singkat berisi link login, dalam bahasa penanya ("id" atau "en"), tanpa konteks apa pun.
def restricted_reply(page: RestrictedPage, lang: str) -> str:
    return REPLIES.get(lang, REPLIES["id"]).format(name=page.name, url=page.url)
