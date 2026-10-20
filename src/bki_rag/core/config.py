"""Central configuration: paths, model choices, and pipeline parameters.

Every value can be overridden with an environment variable (see .env.example).
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")


# Ambil pengaturan dari environment / .env, atau nilai default.
def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


# --- Path ------------------------------------------------------------------
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

# --- Sumber data ----------------------------------------------------------
SITE_URL = "https://www.bki.co.id"
SITEMAP_URL = f"{SITE_URL}/sitemap.xml"
CMS_URL = "https://cms.bki.co.id"
CMS_API = f"{CMS_URL}/api"
# Identitas crawler yang jujur (rancangan meminta User-Agent dengan alamat kontak).
USER_AGENT = _env("CRAWLER_USER_AGENT", "BKI-RAG-Research/0.1 (test crawler; contact: nicholas.tbn26@gmail.com)")
REQUEST_DELAY_S = float(_env("CRAWLER_DELAY_S", "1.0"))
# Tahun laporan yang diambil (tiap laporan tahunan 100-300 halaman; sedikit saja untuk uji coba).
ANNUAL_REPORT_YEARS = [int(y) for y in _env("ANNUAL_REPORT_YEARS", "2024,2023").split(",") if y.strip()]
SUSTAINABILITY_REPORT_LIMIT = int(_env("SUSTAINABILITY_REPORT_LIMIT", "1"))

# --- Model (endpoint apa pun yang kompatibel dengan OpenAI) ----------------------
# Kosong = api.openai.com; mis. https://ai.sumopod.com/v1 untuk gateway SumoPod.
BASE_URL = _env("OPENAI_BASE_URL", "") or None
# Hanya dua model: gpt-5-nano untuk semua tugas teks (jawaban, rewrite pertanyaan, konteks chunk, evaluasi)
# dan text-embedding-3-large untuk embedding. Biaya terukur ±$0,0006 per pertanyaan.
LLM_MODEL = _env("LLM_MODEL", "gpt-5-nano")
# Embedding harus sama dengan model pembuat index (data/index/meta.json), kalau tidak vektor tidak cocok.
EMBED_MODEL = _env("EMBED_MODEL", "text-embedding-3-large")
# Tingkat "berpikir" gpt-5-nano: jawaban sedikit lebih teliti, tugas bantu secepat mungkin.
ANSWER_REASONING = _env("ANSWER_REASONING", "low")
HELPER_REASONING = _env("HELPER_REASONING", "minimal")
LLM_CONCURRENCY = int(_env("LLM_CONCURRENCY", "16"))

# --- Parameter pipeline --------------------------------------------------------
CHUNK_TARGET_TOKENS = int(_env("CHUNK_TARGET_TOKENS", "500"))
CHUNK_MAX_TOKENS = int(_env("CHUNK_MAX_TOKENS", "800"))
CONTEXT_WINDOW_TOKENS = 3000  # potongan dokumen panjang yang dibaca model konteks (hemat batas token/menit)
CANDIDATES_PER_QUERY = int(_env("CANDIDATES_PER_QUERY", "50"))  # per index, per versi pertanyaan
TOP_K = int(_env("TOP_K", "10"))  # jumlah chunk yang dikirim ke model jawaban
RRF_K = 60

# --- Aplikasi web (streamlit_app.py) -------------------------------------------------
APP_PASSWORD = _env("APP_PASSWORD", "")  # kosong = publik; isi agar aplikasi uji coba bersifat privat
DAILY_QUESTION_LIMIT = int(_env("DAILY_QUESTION_LIMIT", "200"))  # semua pengguna digabung: melindungi saldo API
SESSION_QUESTION_LIMIT = int(_env("SESSION_QUESTION_LIMIT", "30"))
MIN_SECONDS_BETWEEN_QUESTIONS = float(_env("MIN_SECONDS_BETWEEN_QUESTIONS", "3"))
MAX_QUESTION_CHARS = int(_env("MAX_QUESTION_CHARS", "500"))
USAGE_FILE = DATA / "usage" / "daily_questions.json"
