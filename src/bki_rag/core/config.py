"""Central configuration: paths, model choices, and pipeline parameters.

Every value can be overridden with an environment variable (see .env.example).
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")


def _env(name: str, default: str) -> str:
    """Setting from the environment / .env, or the default."""
    return os.getenv(name, default)


# --- Paths -----------------------------------------------------------------
DATA = ROOT / "data"
RAW = DATA / "raw"
RAW_SITE = RAW / "site"
RAW_CMS = RAW / "cms"
RAW_PDF = RAW / "pdf"
MANIFEST = RAW / "manifest.jsonl"
PROCESSED = DATA / "processed"
DOCS_FILE = PROCESSED / "docs.jsonl"
CHUNKS_FILE = PROCESSED / "chunks.jsonl"
CLEANING_REPORT = PROCESSED / "cleaning_report.txt"
INDEX_DIR = DATA / "index"
CACHE_DIR = DATA / "cache"
EVAL_DIR = DATA / "eval"
GOLDEN_FILE = EVAL_DIR / "golden.jsonl"
RESULTS_DIR = EVAL_DIR / "results"

# --- Sources ---------------------------------------------------------------
SITE_URL = "https://www.bki.co.id"
SITEMAP_URL = f"{SITE_URL}/sitemap.xml"
CMS_URL = "https://cms.bki.co.id"
CMS_API = f"{CMS_URL}/api"
# Honest crawler identity (the plan asks for a UA with a contact address).
USER_AGENT = _env("CRAWLER_USER_AGENT", "BKI-RAG-Research/0.1 (test crawler; contact: nicholas.tbn26@gmail.com)")
REQUEST_DELAY_S = float(_env("CRAWLER_DELAY_S", "1.0"))
# Report years to ingest (each annual report is 100-300 pages; keep it small for testing).
ANNUAL_REPORT_YEARS = [int(y) for y in _env("ANNUAL_REPORT_YEARS", "2024,2023").split(",") if y.strip()]
SUSTAINABILITY_REPORT_LIMIT = int(_env("SUSTAINABILITY_REPORT_LIMIT", "1"))

# --- Models (any OpenAI-compatible endpoint) ---------------------------------------
# Empty = api.openai.com; e.g. https://ai.sumopod.com/v1 for the SumoPod gateway.
BASE_URL = _env("OPENAI_BASE_URL", "") or None
# Answering: gpt-5-nano measured ~$0.0006 per question (input $0.05, output $0.40 per 1M tokens).
# gpt-5.4-mini scored best in evaluation (0.91 correct) at ~10x the price.
CHAT_MODEL = _env("CHAT_MODEL", "gpt-5-nano")
CHAT_REASONING = _env("CHAT_REASONING", "low")
# Cheap helper tasks: query rewriting, reranking. gpt-5-nano accepts "minimal", not "none".
FAST_MODEL = _env("FAST_MODEL", "gpt-5-nano")
FAST_REASONING = _env("FAST_REASONING", "minimal")
# Chunk contextualisation used to build data/index. Kept separate from FAST_MODEL on purpose: the 1,840
# contexts are cached under this model's name, and changing it makes `index` regenerate (and pay for) all of them.
CONTEXT_MODEL = _env("CONTEXT_MODEL", "gpt-5.4-nano")
CONTEXT_REASONING = _env("CONTEXT_REASONING", "none")
JUDGE_MODEL = _env("JUDGE_MODEL", "gpt-5-mini")
# Must stay the model the index was built with (data/index/meta.json), or query vectors won't match.
EMBED_MODEL = _env("EMBED_MODEL", "text-embedding-3-large")
LLM_CONCURRENCY = int(_env("LLM_CONCURRENCY", "16"))

# --- Pipeline parameters -------------------------------------------------------
CHUNK_TARGET_TOKENS = int(_env("CHUNK_TARGET_TOKENS", "500"))
CHUNK_MAX_TOKENS = int(_env("CHUNK_MAX_TOKENS", "800"))
CONTEXT_WINDOW_TOKENS = 3000  # document slice shown to the contextualiser for long docs (TPM-friendly)
CANDIDATES_PER_QUERY = int(_env("CANDIDATES_PER_QUERY", "50"))  # per index, per query variant
RERANK_POOL = int(_env("RERANK_POOL", "40"))
TOP_K = int(_env("TOP_K", "10"))  # chunks passed to the answer model
RRF_K = 60

# --- Web app (streamlit_app.py) ------------------------------------------------------
APP_PASSWORD = _env("APP_PASSWORD", "")  # empty = public; set it to keep a test deployment private
DAILY_QUESTION_LIMIT = int(_env("DAILY_QUESTION_LIMIT", "200"))  # all users together: protects the API balance
SESSION_QUESTION_LIMIT = int(_env("SESSION_QUESTION_LIMIT", "30"))
MIN_SECONDS_BETWEEN_QUESTIONS = float(_env("MIN_SECONDS_BETWEEN_QUESTIONS", "3"))
MAX_QUESTION_CHARS = int(_env("MAX_QUESTION_CHARS", "500"))
USAGE_FILE = DATA / "usage" / "daily_questions.json"
