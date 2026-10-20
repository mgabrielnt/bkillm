# BKI RAG Chatbot

Chatbot tanya-jawab atas konten publik **bki.co.id** (PT Biro Klasifikasi Indonesia): situs, berita, halaman ESG,
dan laporan tahunan/keberlanjutan. Setiap jawaban disertai link sumbernya. Tersedia sebagai UI web (Streamlit)
dan chatbot terminal. Model dipanggil lewat API yang kompatibel dengan OpenAI (saat ini gateway SumoPod).

Hanya dua model yang dipakai:

| Model | Untuk |
|---|---|
| `gpt-5-nano` | semua tugas teks: jawaban, rewrite pertanyaan, konteks chunk, evaluasi |
| `text-embedding-3-large` | embedding (multilingual EN/ID) |

Pencarian menggabungkan embedding dan BM25 (kata persis) dengan Reciprocal Rank Fusion.

**Biaya terukur** (tagihan nyata SumoPod): rata-rata **$0,0006 (±Rp10) per pertanyaan**; ±Rp10.000 per 1.000
pertanyaan. Sebagian besar untuk membaca 10 potongan sumber (±6.900 token input) dan token "berpikir" model,
bukan panjang pertanyaan/jawaban.

## Struktur folder

Aturan: setiap file maksimal 100 baris, satu tugas per file, setiap fungsi punya komentar singkat Bahasa Indonesia
tepat di atas `def`/`class`, dan setiap folder punya `__init__.py` yang menjelaskan isinya.

```
bki/
├── streamlit_app.py              # pembuka UI web (isi halaman ada di src/bki_rag/app/web/)
├── requirements.txt              # paket runtime (dipakai Streamlit Cloud)
├── pyproject.toml                # paket bki_rag; extras: [web], [ingest]
├── .env.example                  # contoh konfigurasi lokal (.env tidak di-commit)
├── .streamlit/                   # config.toml (aman untuk publik) + contoh Secrets
├── src/bki_rag/
│   ├── cli.py                    # python -m bki_rag <perintah>
│   ├── core/                     # dasar bersama
│   │   ├── config.py             #   path, 2 model, parameter (bisa diubah lewat .env / Secrets)
│   │   ├── llm.py                #   client OpenAI-compatible: chat, JSON, embedding, retry
│   │   └── utils.py              #   JSONL, hash, hitung token, normalisasi teks
│   ├── prompts/                  # SEMUA prompt, satu file per tahap
│   │   ├── indexing.py           #   konteks chunk + glosarium
│   │   ├── retrieval.py          #   rewrite pertanyaan
│   │   ├── answer.py             #   system prompt chatbot
│   │   └── evaluation.py         #   golden set + juri
│   ├── ingestion/                # Tahap 1-4: situs -> chunk bersih
│   │   ├── crawl/                #   fetcher.py, cms.py, site.py, pdfs.py
│   │   ├── extract/              #   rsc.py, rsc_text.py, i18n.py, urls.py, pages.py, tiptap.py, cms.py, pdf.py
│   │   ├── clean/                #   filters.py (boilerplate), dedup.py (exact + MinHash)
│   │   ├── chunk/                #   units.py (paragraf, split), chunker.py (packing + metadata)
│   │   └── pipeline.py           #   perintah `process`
│   ├── indexing/                 # Tahap 5: contextualize.py, store.py, pipeline.py, inspect.py
│   ├── retrieval/                # Tahap 6a: restricted.py, query.py, retriever.py
│   ├── generation/               # Tahap 6b: sources.py, citations.py, answer.py
│   ├── evaluation/               # golden.py, retrieval_eval.py, judge.py, runner.py
│   └── app/
│       ├── terminal.py           #   chatbot terminal (`chat` / `ask`)
│       └── web/                  #   page.py, views.py, limits.py, errors.py (Streamlit)
└── data/
    ├── index/                    # index yang dipakai aplikasi (di-commit, ±34 MB)
    ├── processed/                # dokumen & chunk bersih + laporan pembersihan
    ├── eval/                     # golden.jsonl (hasil evaluasi ditulis ke eval/results/)
    ├── raw/                      # hasil crawl mentah (lokal saja)
    └── cache/                    # cache berbayar: konteks, embedding, parsing PDF (lokal saja)
```

`data/raw/` dan `data/cache/` tidak ada di GitHub, tapi **jangan dihapus di lokal**: isinya membuat proses ulang
gratis (konteks dan embedding 1.840 chunk sudah dibayar).

## Cara pakai (lokal, PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[web,ingest]"
copy .env.example .env      # isi OPENAI_API_KEY
```

```powershell
streamlit run streamlit_app.py   # UI web di http://localhost:8501
python -m bki_rag chat           # chatbot terminal (/debug, /reset, /exit)
python -m bki_rag ask "Berapa lama sertifikat garis muat berlaku?"
```

Membangun ulang data (hanya bila situs berubah):

```powershell
python -m bki_rag crawl     # ±3 menit, sopan 1 request/detik
python -m bki_rag process   # ekstraksi, pembersihan, chunking (gratis)
python -m bki_rag index     # konteks + embedding; hanya chunk baru/berubah yang dibayar
```

Evaluasi (berbayar; `--limit` = sampel kecil yang murah):

```powershell
python -m bki_rag eval --answers --limit 30
```

## Halaman yang butuh login

Semua pertanyaan tentang **rules dan regulasi** langsung diarahkan ke
https://www.bki.co.id/research/rnd/bki-rules-regulations (halaman yang butuh login), **tanpa pencarian apa pun**:
tidak ada embedding, tidak ada retrieval, dan tidak ada panggilan model, jadi biayanya nol.

Deteksinya (`retrieval/restricted.py`) cukup mencocokkan kata kunci di pertanyaan: rule(s), regulation(s) /
regulatory, aturan, peraturan, regulasi, ketentuan, pedoman, guideline(s), guidance, standar teknis, technical
standard, termasuk bentuk berakhiran seperti "peraturannya" atau "aturan-aturan". Balasan memakai bahasa penanya.
Uji 19 pertanyaan campuran: 19/19 benar. Untuk menambah halaman login lain, tambahkan `RestrictedPage` baru ke
`RESTRICTED_PAGES`.

## Melihat isi vektor embedding

Vektor tersimpan di `data/index/`:

| File | Isi |
|---|---|
| `embeddings.npy` | matriks float32 1840 × 3072 (`text-embedding-3-large`); satu baris = satu chunk, sudah dinormalisasi (panjang 1) sehingga dot product = cosine similarity |
| `chunks.jsonl` | teks + metadata tiap chunk, urutannya sama dengan baris matriks (baris i = baris ke-i file ini) |
| `meta.json` | model embedding dan jumlah chunk |
| `bm25/` | index kata kunci (BM25) untuk chunk yang sama |

Cara membukanya (gratis, tanpa API):

```powershell
python -m bki_rag vectors                                  # info index + vektor chunk pertama + chunk termirip
python -m bki_rag vectors --chunk service-13d66e12-000     # chunk tertentu (id dari chunks.jsonl)
python -m bki_rag vectors --export vektor.csv --rows 20    # 20 vektor lengkap ke CSV (buka di Excel)
python -m bki_rag vectors --query "masa berlaku sertifikat garis muat"   # cari dengan teks (biaya ±Rp0,03)
```

Atau langsung di Python: `numpy.load("data/index/embeddings.npy")`.

## Deploy (Streamlit Community Cloud)

1. Repo GitHub: `.env`, `.streamlit/secrets.toml`, `data/raw/`, `data/cache/` tidak ikut; `data/index/` ikut.
2. share.streamlit.io → New app → repo ini, main file `streamlit_app.py`.
3. Settings → Secrets, minimal:
   ```toml
   OPENAI_API_KEY = "sk-..."
   OPENAI_BASE_URL = "https://ai.sumopod.com/v1"
   ```
4. Pasang batas belanja di dashboard SumoPod sebagai pengaman kedua.

Pengaman di aplikasi: API key hanya dari Secrets/env; batas 200 pertanyaan/hari untuk semua pengguna
(`DAILY_QUESTION_LIMIT`, reset bila server restart); per sesi maks 30 pertanyaan, jeda 3 detik, maks 500 karakter;
jawaban dirender tanpa HTML; error ditampilkan tanpa detail teknis; `APP_PASSWORD` opsional; keterangan bahwa ini
bukan kanal resmi BKI.

## Alur data

1. **Crawl** (`ingestion/crawl/`). bki.co.id adalah aplikasi Next.js di belakang WAF dengan CMS Strapi publik
   (`cms.bki.co.id/api`). Berita (EN 80 + ID 73), artikel, event, 58 halaman ESG (EN+ID), lowongan, dan daftar
   laporan diambil dari API JSON. Halaman statis diambil sebagai HTML dengan User-Agent jujur; halaman login
   dilewati; tidak ada upaya mengakali WAF. 22 URL "R&D activities" di sitemap ternyata halaman kosong.
2. **Ekstraksi** (`ingestion/extract/`). Teks halaman statis ada di kamus i18n dalam payload React Server
   Components (EN) dan `/locales/id/common.json` (ID); tiap namespace jadi satu dokumen dengan URL-nya. PDF
   (laporan tahunan 2024 & 2023, laporan keberlanjutan 2024, kebijakan HSE) diparse per halaman untuk sitasi.
3. **Pembersihan** (`ingestion/clean/`). Filter boilerplate dua bahasa, filter frekuensi lintas dokumen,
   header/footer PDF, normalisasi Unicode, dedup exact + MinHash, buang dokumen < 50 kata.
4. **Chunking** (`ingestion/chunk/`). Per heading, ±500 token, tabel utuh, breadcrumb di awal tiap chunk.
5. **Indexing** (`indexing/`). Tiap chunk diberi 1-3 kalimat konteks dua bahasa, lalu di-embed dan masuk BM25.
6. **Retrieval + jawaban** (`retrieval/`, `generation/`). Pertanyaan ditulis ulang (mandiri + EN + ID + kata
   kunci), dicari dengan vektor dan BM25, digabung RRF; 10 chunk teratas diberi label "halaman situs aktif" atau
   "laporan tahun X", lalu model menjawab hanya dari sumber, bersitasi, dalam bahasa penanya, atau menolak.

## Hasil evaluasi

Golden set (`data/eval/golden.jsonl`): 103 pertanyaan dari 12 tipe dokumen (60% pendek gaya chat, ±50% lintas
bahasa) + 20 pertanyaan jebakan yang harus ditolak. Pencarian menemukan dokumen yang benar di 10 teratas untuk
99% pertanyaan. Kualitas jawaban `gpt-5-nano` baru diuji manual; untuk mengukurnya jalankan
`python -m bki_rag eval --answers --limit 30` (berbayar, ±Rp5.000).

Catatan terbuka: perbaikan halaman Company Profile (visi-misi terbaru, biografi direksi) sudah ada di
`data/processed/`, tetapi 34 chunk-nya belum masuk `data/index/` (perlu `python -m bki_rag index`, ±Rp200).
