# BKI RAG Chatbot (terminal)

Chatbot tanya-jawab atas konten publik **bki.co.id** (PT Biro Klasifikasi Indonesia), dibangun mengikuti
dokumen rancangan "Rancangan Chatbot RAG untuk bki.co.id". Semua model memakai OpenAI.

| Komponen | Pilihan |
|---|---|
| Jawaban chatbot | `gpt-5.4-mini` (reasoning low) |
| Contextual retrieval, query rewrite, rerank | `gpt-5.4-nano` (reasoning none) |
| Embedding | `text-embedding-3-large` (multilingual EN/ID) |
| Pencarian kata persis | BM25 (`bm25s`) + Reciprocal Rank Fusion |
| Juri evaluasi + pembuat golden set | `gpt-5.4-mini` |

## Struktur folder

```
bki/
├── .env                  # OPENAI_API_KEY (tidak di-commit)
├── .env.example          # semua variabel yang bisa diubah
├── requirements.txt
├── README.md
├── pyproject.toml        # paket bki_rag (pip install -e .)
├── src/bki_rag/
│   ├── cli.py                # python -m bki_rag <perintah>
│   ├── prompts.py            # SEMUA prompt LLM di satu file (tempat prompt engineering)
│   ├── core/                 # dipakai semua tahap
│   │   ├── config.py         #   path, model, parameter (override lewat .env)
│   │   ├── llm.py            #   wrapper OpenAI: chat, JSON, embedding, paralel + retry rate-limit
│   │   └── utils.py          #   JSONL, hash, hitung token, normalisasi teks
│   ├── ingestion/            # Tahap 1-4: dari situs ke chunk
│   │   ├── crawl.py          #   sitemap, CMS API, PDF + manifest
│   │   ├── extract.py        #   payload RSC Next.js, kamus i18n, CMS, PDF -> Markdown
│   │   ├── clean.py          #   boilerplate berlapis, dedup exact + MinHash
│   │   ├── chunk.py          #   chunk per heading + breadcrumb + metadata
│   │   └── pipeline.py       #   orkestrasi (perintah `process`)
│   ├── indexing/             # Tahap 5: dari chunk ke index
│   │   ├── contextualize.py  #   contextual retrieval (deskripsi chunk 2 bahasa, di-cache)
│   │   ├── store.py          #   index di disk: embedding + BM25 + metadata
│   │   └── pipeline.py       #   orkestrasi (perintah `index`)
│   ├── retrieval/            # Tahap 6a: dari pertanyaan ke chunk
│   │   ├── query.py          #   rewrite pertanyaan: mandiri + versi EN/ID + kata kunci + bahasa
│   │   ├── retriever.py      #   hybrid vektor + BM25, Reciprocal Rank Fusion
│   │   └── rerank.py         #   reranker LLM (opsional, default mati, lihat hasil evaluasi)
│   ├── generation/
│   │   └── answer.py         # Tahap 6b: jawaban bersitasi
│   ├── evaluation/
│   │   ├── golden.py         #   pembuatan golden set + 20 pertanyaan jebakan
│   │   ├── judge.py          #   LLM juri: benar, setia sumber, sitasi, penolakan
│   │   └── runner.py         #   tangga eksperimen + metrik retrieval (perintah `eval`)
│   └── app/
│       └── chat.py           # chatbot terminal (perintah `chat` / `ask`)
└── data/
    ├── raw/              # hasil crawl mentah + manifest.jsonl
    ├── processed/        # docs.jsonl, chunks.jsonl, cleaning_report.txt
    ├── cache/            # cache konteks, embedding, hasil parsing PDF
    ├── index/            # index final (kontekstual)
    ├── index_plain/      # index baseline (tanpa konteks) untuk eksperimen
    └── eval/             # golden.jsonl + results/
```

## Cara pakai

Setup sekali (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[web,ingest]"   # paket bki_rag + Streamlit + alat crawl/parsing
copy .env.example .env    # lalu isi OPENAI_API_KEY
```

Setelah venv aktif, perintah sama di PowerShell maupun bash (tidak perlu `PYTHONPATH`):

```powershell
streamlit run streamlit_app.py   # UI web di http://localhost:8501
python -m bki_rag chat      # chatbot terminal
python -m bki_rag ask "Berapa lama sertifikat garis muat berlaku?"
python -m bki_rag crawl     # ~3 menit (sopan, 1 request/detik)
python -m bki_rag process   # ~7 menit pertama kali (parsing PDF), lalu detik
python -m bki_rag index     # contextual retrieval + embedding (di-cache)
```

Di dalam chat: `/debug` menampilkan chunk yang terambil, `/reset` menghapus riwayat, `/exit` keluar.

Evaluasi (memakai kredit OpenAI; `--limit` untuk sampel kecil yang murah):

```powershell
python -m bki_rag eval --config full --answers --limit 30   # retrieval + jawaban + juri
python -m bki_rag eval --config all                         # tangga eksperimen retrieval saja
python -m bki_rag golden                                    # buat ulang golden set
```

## Deploy (Streamlit Community Cloud)

1. Push folder ini ke repo GitHub (boleh private). `.env`, `.streamlit/secrets.toml`, `data/raw/` dan `data/cache/`
   tidak ikut ter-upload (lihat `.gitignore`); `data/index/` (~34 MB) **harus** ikut karena dipakai aplikasi.
2. Di share.streamlit.io: New app, pilih repo, main file `streamlit_app.py`.
3. Settings > Secrets: tempel isi `.streamlit/secrets.toml.example` dengan API key Anda.
4. Deploy. `requirements.txt` hanya berisi paket runtime (tanpa crawler/parser PDF).

Pengaman yang sudah ada di aplikasi:
- API key hanya dari secrets/env, tidak pernah ditampilkan.
- `DAILY_QUESTION_LIMIT` (default 200/hari untuk semua pengguna) melindungi saldo API. Pasang juga batas belanja
  di dashboard penyedia API, karena penghitung ini ter-reset jika server restart.
- Per sesi: maksimal `SESSION_QUESTION_LIMIT` (30) pertanyaan, jeda 3 detik, pertanyaan maks 500 karakter.
- Jawaban dirender sebagai Markdown biasa (tanpa HTML); error internal hanya dicatat di log server.
- `APP_PASSWORD` (opsional) membuat aplikasi hanya bisa dibuka dengan kata sandi.
- Keterangan di halaman: bukan kanal resmi BKI.

## Alur data

1. **Crawl** (`ingestion/crawl.py`). Situs bki.co.id adalah aplikasi Next.js di belakang WAF, dengan CMS Strapi publik
   di `cms.bki.co.id/api`. Berita (EN 80 + ID 73), artikel, event, 58 halaman ESG (EN+ID), lowongan, dan daftar
   laporan diambil dari API JSON (bersih, tanpa navbar). Halaman statis diambil sebagai HTML biasa dengan
   User-Agent jujur. Halaman yang redirect ke `/login` ditandai `auth_required` dan dilewati.
   Browser headless tidak dipakai: konten sudah ada di payload server, dan tidak ada upaya mengakali WAF.
2. **Ekstraksi** (`ingestion/extract.py`). Teks halaman statis tersimpan di kamus i18n yang tertanam di payload React Server
   Components (EN) dan di `/locales/id/common.json` (ID); setiap namespace (mis. `statutory.loadLine`) menjadi satu
   dokumen yang dipetakan ke URL-nya. PDF (laporan tahunan 2024 & 2023, laporan keberlanjutan 2024, kebijakan HSE)
   diparse dengan `pymupdf4llm` per halaman agar sitasi bisa menyebut nomor halaman.
3. **Pembersihan** (`ingestion/clean.py`). Filter baris boilerplate dua bahasa, filter frekuensi lintas dokumen (blok yang
   muncul di >20% dokumen, atau ≥5 dokumen dan pendek), header/footer PDF per dokumen, normalisasi Unicode,
   dedup exact (sha256) dan near-duplicate (MinHash LSH, J≥0,8), gerbang kualitas ≥50 kata.
   Laporan untuk dicek manual: `data/processed/cleaning_report.txt`.
4. **Chunking** (`ingestion/chunk.py`). Per heading, ~500 token (maks 800), tabel tidak dipotong di tengah baris, dokumen
   pendek tetap satu chunk, breadcrumb `Judul > Bagian > Subbagian` di awal setiap chunk, overlap kecil hanya bila
   memotong di tengah bagian.
5. **Indexing** (`indexing/`). Setiap chunk diberi 1-3 kalimat konteks oleh `gpt-5.4-nano` (istilah kunci dua
   bahasa + glosarium SOLAS/MARPOL/ISM/...), lalu konteks+chunk di-embed dan dimasukkan ke BM25.
6. **Retrieval + jawaban** (`retrieval/`, `generation/`). Pertanyaan ditulis ulang menjadi pertanyaan mandiri +
   versi EN + versi ID + kata kunci; vektor dan BM25 dicari untuk setiap versi lalu digabung dengan RRF;
   10 chunk teratas dikirim ke `gpt-5.4-mini` yang wajib menjawab hanya
   dari sumber, bersitasi [n], dalam bahasa penanya, dan menolak bila informasi tidak ada.

## Hasil evaluasi

Golden set: 103 pertanyaan dari 12 tipe dokumen (60% pendek gaya chat, ~50% lintas bahasa) + 20 pertanyaan
jebakan yang harus ditolak. Pertanyaan dibuat oleh LLM dari chunk acak, jadi angkanya cenderung optimis;
uji juga dengan pertanyaan pengguna sungguhan.

Retrieval (hit@k = dokumen sumber yang benar ada di k teratas):

| Konfigurasi | hit@1 | hit@5 | hit@10 | MRR | lintas bahasa hit@10 |
|---|---|---|---|---|---|
| vector (embedding saja) | 0,728 | 0,971 | 0,981 | 0,824 | 1,000 |
| hybrid (+ BM25, RRF) | 0,748 | 0,932 | 0,961 | 0,839 | 0,966 |
| hybrid_ctx (+ contextual retrieval) | 0,786 | 0,961 | 0,981 | 0,861 | 0,983 |
| **full** (+ rewrite EN/ID) — default | 0,786 | 0,971 | 0,990 | 0,867 | 1,000 |
| full_rerank (+ rerank nano) | 0,777 | 0,922 | 0,951 | 0,844 | 0,966 |

Jawaban (dinilai `gpt-5.4-mini`, 123 pertanyaan):

| Konfigurasi | benar | setia sumber | sitasi | salah tolak | jebakan ditolak | latensi |
|---|---|---|---|---|---|---|
| full | 0,913 | 0,805 | 0,981 | 2,9% | 100% | 3,7 dtk |
| full_rerank | 0,888 | 0,821 | 0,990 | 3,9% | 100% | 5,8 dtk |

Keputusan: reranker dimatikan (lebih lambat dan tidak lebih akurat). Setelah tabel ini, prompt diperbaiki
(bahasa jawaban dikunci, larangan menambah pengetahuan umum, utamakan sumber terbaru) dan juri diberi chunk
lengkap + tanggal. **Perbaikan itu belum diukur ulang**; jalankan:

```powershell
python -m bki_rag eval --config full --answers --limit 30
```
