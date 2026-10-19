"""Map dictionary namespaces to page URLs (for citations) and URLs to document types."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from ...core import config as C

# Namespace -> path where the fuzzy match below would be ambiguous or wrong.
NAMESPACE_URLS: dict[str, str] = {
    "home": "/", "homepage": "/", "hero": "/", "e_certificate_drawer": "/",
    "aboutUs": "/company-profile", "companyProfile": "/company-profile", "boc": "/company-profile",
    "statutory": "/our-services/statutory", "countryFile": "/our-services/statutory",
    "flagStateServices": "/our-services/statutory/statutory-flag-state-services",
    "statutoryFlagState": "/our-services/statutory/statutory-flag-state-services",
    "ism": "/our-services/statutory/international-safety-management",
    "ismRegister": "/our-services/statutory/international-safety-management/ism-register",
    "ismRegisterSmc": "/our-services/statutory/international-safety-management/ism-register-smc",
    "isps": "/our-services/statutory/international-ship-port-facility-security",
    "ispsRegister": "/our-services/statutory/international-ship-port-facility-security/isps-register",
    "psc": "/our-services/statutory/port-state-control",
    "portStateControl": "/our-services/statutory/port-state-control",
    "mlc": "/our-services/statutory/maritime-labour-convention",
    "bwm": "/our-services/statutory/ballast-water-management",
    "register": "/our-services/classification/ship-register",
    "privacyPolicy": "/privacy-policy/en", "wbs": "/esgrc/wbs", "gcg": "/esgrc/good-corporate-governance",
    "csr": "/esgrc/corporate-social-responsibility", "esgrcCSR": "/esgrc/corporate-social-responsibility",
    "csrPage": "/esgrc/corporate-social-responsibility",
    "esgrcEnvironment": "/esgrc/environment", "environmentPage": "/esgrc/environment",
    "rnd": "/research/rnd", "rulesRegulations": "/research/rnd/bki-rules-regulations",
    "sustainabilityPage": "/sustainability-report",
}

_DOC_TYPES = (("/our-services", "service"), ("/news", "news"), ("/articles", "article"), ("/research", "research"),
              ("/esgrc", "esg"), ("/privacy-policy", "policy"), ("/our-policy", "policy"), ("/events", "event"))


def _words(key: str) -> set[str]:
    """Lowercase words of a key or path segment (camelCase and kebab-case split)."""
    key = re.sub(r"([a-z])([A-Z])", r"\1 \2", key)
    return {w for w in re.split(r"[^a-zA-Z0-9]+", key.lower()) if w}


def map_namespace_url(ns: str, site_paths: list[str]) -> str:
    """Best matching sitemap URL for a namespace name (word overlap), or the home page."""
    if ns in NAMESPACE_URLS:
        return C.SITE_URL + NAMESPACE_URLS[ns]
    nw = _words(ns)
    best, best_score = "/", 0.0
    for path in site_paths:
        segs = [s for s in path.strip("/").split("/") if s]
        if not segs:
            continue
        last = _words(segs[-1])
        allw = set().union(*(_words(s) for s in segs))
        score = len(nw & last) / len(nw | last) + 0.25 * len(nw & allw) / max(len(nw), 1)
        if score > best_score:
            best, best_score = path, score
    return C.SITE_URL + (best if best_score >= 0.5 else "/")


def doc_type_from_url(url: str) -> str:
    """Document type (service, news, esg, ...) from the URL path."""
    path = urlparse(url).path
    return next((kind for prefix, kind in _DOC_TYPES if path.startswith(prefix)), "company")
