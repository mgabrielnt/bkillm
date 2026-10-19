"""Questions about pages behind BKI's login are answered with a link to log in, without any context.

A question is routed to a restricted page when it contains a rule keyword AND its embedding is similar
enough to the page description (RESTRICTED_MIN_SIM), or when the similarity alone is very high
(RESTRICTED_STRONG_SIM). Measured on test questions: every BKI-rules question had similarity >= 0.558 and a
rule keyword; other BKI questions reached up to 0.653 but had no rule keyword.
"""
from __future__ import annotations

import re
from functools import lru_cache

import numpy as np

from ..core import config as C
from ..core.llm import embed

RESTRICTED_PAGES = [{
    "name": "BKI Rules & Regulations",
    "url": "https://www.bki.co.id/research/rnd/bki-rules-regulations",
    "keywords": re.compile(r"\b(rules?|regulations?|aturan|peraturan|ketentuan|pedoman|guidance|guidelines?|"
                           r"standar teknis|technical standards?)\b", re.I),
    "anchors": [  # page text from the site + paraphrases and typical questions, used for the embedding
        "BKI held the classification activities based on the latest rules, guidelines, and technical standard. "
        "In order to provide better service, our team continuously develop BKI Rules and Regulation through "
        "current research and practical maritime experiences. The development is also based on the "
        "interpretation from IACS, IMO regulation and other relevant standard so that the rules is comply with "
        "the applicable international regulations.",
        "BKI Rules and Regulations: rules, guidelines and technical standards for ship classification, "
        "developed from research, IACS interpretations and IMO regulations.",
        "Aturan dan Peraturan BKI (BKI Rules and Regulations): aturan, pedoman, dan standar teknis klasifikasi "
        "kapal yang dikembangkan BKI berdasarkan riset, interpretasi IACS, dan regulasi IMO.",
        "Di mana saya bisa membaca atau mengunduh BKI Rules and Regulations?",
        "What do the BKI rules say about hull construction requirements?",
    ],
}]

REPLY = {
    "id": "Informasi tentang {name} hanya tersedia bagi pengguna terdaftar. Anda bisa mengaksesnya dengan "
          "login di: {url}",
    "en": "Information about {name} is only available to registered users. You can access it by logging in "
          "at: {url}",
}


# Vektor embedding anchor setiap halaman (dihitung sekali per proses).
@lru_cache(maxsize=1)
def _anchor_vectors() -> list[np.ndarray]:
    return [embed(page["anchors"], model=C.EMBED_MODEL) for page in RESTRICTED_PAGES]


# Halaman login yang cocok dengan pertanyaan (dict halaman), atau None jika pertanyaan biasa.
def match_restricted(question: str) -> dict | None:
    qvec = embed([question], model=C.EMBED_MODEL)[0]
    for page, anchors in zip(RESTRICTED_PAGES, _anchor_vectors()):
        sim = float((anchors @ qvec).max())
        has_keyword = bool(page["keywords"].search(question))
        if (has_keyword and sim >= C.RESTRICTED_MIN_SIM) or sim >= C.RESTRICTED_STRONG_SIM:
            return page
    return None


# Balasan singkat berisi link login, dalam bahasa penanya, tanpa konteks apa pun.
def restricted_reply(page: dict, lang: str) -> str:
    return REPLY.get(lang, REPLY["id"]).format(name=page["name"], url=page["url"])
