# BKI RAG Chatbot

Chatbot tanya-jawab atas konten publik **bki.co.id** (PT Biro Klasifikasi Indonesia): halaman situs, berita,
halaman ESG, dan laporan tahunan/keberlanjutan. Setiap jawaban disertai sumbernya. Tersedia sebagai UI web
(Streamlit) dan chatbot terminal.

| Dokumen | Isi |
|---|---|
| **README.md** (ini) | Gambaran, cara menjalankan, konfigurasi, struktur folder, deploy |
| [docs/alur-pertanyaan.md](docs/alur-pertanyaan.md) | Apa yang terjadi di kode untuk satu pertanyaan, langkah demi langkah |
| [docs/pembuatan-data.md](docs/pembuatan-data.md) | Dari situs sampai index: crawl, ekstraksi, pembersihan, chunking, indexing |
| [docs/pengembangan.md](docs/pengembangan.md) | Konvensi kode, cara menambah fitur, evaluasi, pemecahan masalah |

## Cara kerja singkat

```
 Data (dibuat sekali)                          Setiap pertanyaan
 ─────────────────────                         ─────────────────
 bki.co.id ─► crawl ─► extract ─► clean        pertanyaan
              ─► chunk ─► index                   │ topik rules/regulasi? ─► link login (tanpa API)
              (data/index/)                       ▼
                    │                          rewrite* ─► embedding ─► vektor + BM25 ─► RRF ─► 10 chunk
                    └── dibaca saat start ──►                                                   │
                                               model menjawab dari 10 chunk, dengan sitasi [n] ◄┘
                                                  │
                                               sitasi dirapikan ─► jawaban + daftar sumber
```

\* Rewrite pertanyaan hanya untuk pertanyaan lanjutan (ada riwayat chat). Pertanyaan pertama langsung dicari.

Hanya dua model, keduanya lewat API yang kompatibel dengan OpenAI:

| Model | Untuk |
|---|---|
| `gpt-5-nano` | semua tugas teks: jawaban, rewrite pertanyaan, konteks chunk, juri evaluasi |
| `text-embedding-3-large` | embedding (EN/ID). **Harus sama dengan model pembuat index** (`data/index/meta.json`) |

Pencarian menggabungkan kemiripan makna (embedding) dan kata persis (BM25) dengan Reciprocal Rank Fusion.
Tidak ada reranker.

## Menjalankan

Persiapan (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[web,ingest]"
copy .env.example .env      # isi OPENAI_API_KEY (dan OPENAI_BASE_URL bila memakai gateway)
```

Memakai chatbot (index sudah ada di `data/index/`, tidak perlu crawl):

```powershell
streamlit run streamlit_app.py                        # UI web di http://localhost:8501
python -m bki_rag chat                                # terminal interaktif (/debug, /reset, /exit)
python -m bki_rag ask "Berapa lama sertifikat garis muat berlaku?"
```

Membangun ulang data (hanya bila isi situs berubah; detail di [docs/pembuatan-data.md](docs/pembuatan-data.md)):

```powershell
python -m bki_rag crawl     # unduh situs, CMS, PDF (±3 menit, 1 request/detik)
python -m bki_rag process   # ekstraksi, pembersihan, chunking (gratis)
python -m bki_rag index     # konteks + embedding + BM25; hanya chunk baru/berubah yang dibayar
```

Evaluasi dan pemeriksaan (detail di [docs/pengembangan.md](docs/pengembangan.md)):

```powershell
python -m bki_rag eval --answers --limit 30 --workers 1   # berbayar; --workers 1 = waktu akurat
python -m bki_rag vectors                                 # lihat isi index (gratis)
```

## Konfigurasi

Semua pengaturan ada di [src/bki_rag/core/config.py](src/bki_rag/core/config.py) dan bisa diubah lewat `.env`
(lokal) atau Streamlit Secrets (cloud). Contoh lengkap: [.env.example](.env.example).

| Pengaturan | Bawaan | Artinya |
|---|---|---|
| `OPENAI_API_KEY` | – | **Wajib.** Hanya dari env/Secrets, tidak pernah ditampilkan |
| `OPENAI_BASE_URL` | kosong | Kosong = api.openai.com; isi untuk gateway lain |
| `ANSWER_REASONING` | `minimal` | Seberapa lama model "berpikir" saat menjawab. `low` = lebih teliti, lebih lambat |
| `RETRY_REASONING` | `low` | Jawaban "tidak ditemukan" diulang dengan tingkat ini (kosong = tidak diulang) |
| `STREAM_ANSWER` | `1` | Jawaban tampil sedikit demi sedikit |
| `REWRITE_FIRST_QUESTION` | `0` | `1` = pertanyaan pertama juga di-rewrite (lebih lambat) |
| `QUERY_EMBED_TIMEOUT_S` | `2` | Embedding pertanyaan yang tersendat lebih dari ini diulang |
| `TOP_K` | `10` | Jumlah chunk yang dikirim ke model jawaban |
| `APP_PASSWORD` | kosong | Isi agar UI web butuh kata sandi |
| `DAILY_QUESTION_LIMIT` | `200` | Batas pertanyaan per hari, semua pengguna digabung |
| `SESSION_QUESTION_LIMIT` | `30` | Batas pertanyaan per sesi pengunjung |

## Struktur folder

```
bki/
├── streamlit_app.py          pembuka UI web (isi halaman di src/bki_rag/app/web/)
├── requirements.txt          paket runtime (dipakai Streamlit Cloud)
├── pyproject.toml            paket bki_rag; extras: [web], [ingest]
├── .env.example              contoh konfigurasi (.env tidak di-commit)
├── .streamlit/               config.toml (aman untuk publik) + contoh Secrets
├── docs/                     dokumentasi (lihat tabel di atas)
├── src/bki_rag/
│   ├── cli.py                python -m bki_rag <perintah>
│   ├── core/                 dasar bersama: config.py, llm.py, usage.py, utils.py
│   ├── prompts/              SEMUA prompt, satu file per tahap
│   ├── ingestion/            Tahap 1-4: crawl/ extract/ clean/ chunk/ + pipeline.py
│   ├── indexing/             Tahap 5: contextualize.py, store.py, pipeline.py, inspect.py, export.py
│   ├── retrieval/            Tahap 6a: restricted.py, query.py, retriever.py
│   ├── generation/           Tahap 6b: sources.py, reply.py, citations.py, answer.py
│   ├── evaluation/           golden.py, retrieval_eval.py, answer_eval.py, judge.py, guard.py, report.py, runner.py
│   └── app/                  terminal.py dan web/ (page.py, views.py, scroll.py, limits.py, errors.py)
└── data/
    ├── index/                index yang dipakai aplikasi (di-commit, ±34 MB)
    ├── processed/            dokumen & chunk bersih + laporan pembersihan
    ├── eval/                 golden.jsonl; hasil evaluasi di eval/results/
    ├── raw/                  hasil crawl mentah (hanya lokal)
    └── cache/                cache berbayar: konteks, embedding, parsing PDF (hanya lokal)
```

`data/raw/` dan `data/cache/` tidak ada di GitHub, tetapi **jangan dihapus di lokal**: isinya membuat proses ulang
gratis (konteks dan embedding sudah dibayar).

File di `data/index/` yang dibaca aplikasi:

| File | Isi |
|---|---|
| `chunks.jsonl` | teks + metadata tiap chunk (baris ke-i = vektor baris ke-i) |
| `embeddings.npy` | matriks float32 (jumlah chunk × 3072), sudah dinormalisasi |
| `bm25/` | index kata kunci |
| `meta.json` | nama model embedding dan jumlah chunk |

## Halaman yang butuh login

Pertanyaan tentang **rules dan regulasi** langsung dijawab dengan link
https://www.bki.co.id/research/rnd/bki-rules-regulations (halaman itu butuh login), tanpa embedding, tanpa
pencarian, tanpa panggilan model. Deteksinya pencocokan kata kunci di
[retrieval/restricted.py](src/bki_rag/retrieval/restricted.py). Untuk menambah halaman login lain, tambahkan
`RestrictedPage` baru ke `RESTRICTED_PAGES`.

## Deploy (Streamlit Community Cloud)

1. Repo GitHub: `.env`, `.streamlit/secrets.toml`, `data/raw/`, `data/cache/` tidak ikut; `data/index/` ikut.
2. share.streamlit.io → New app → repo ini, main file `streamlit_app.py`.
3. Settings → Secrets, minimal:
   ```toml
   OPENAI_API_KEY = "sk-..."
   OPENAI_BASE_URL = "https://ai.sumopod.com/v1"
   ```
4. Pasang batas belanja di dashboard penyedia API sebagai pengaman kedua.

Pengaman di aplikasi: API key hanya dari Secrets/env; 200 pertanyaan/hari untuk semua pengguna (hitungannya
reset bila server restart); per sesi maksimal 30 pertanyaan, jeda 3 detik, 500 karakter; jawaban dirender tanpa
HTML; error ditampilkan tanpa detail teknis; `APP_PASSWORD` opsional; ada keterangan bahwa ini bukan kanal resmi BKI.

## Hasil evaluasi terakhir

Golden set: 123 pertanyaan (`data/eval/golden.jsonl`), termasuk pertanyaan jebakan yang harus ditolak.
Hasil run 60 soal dengan pengaturan bawaan sekarang (`--workers 1`):

| Metrik | Hasil | Target |
|---|---|---|
| Dokumen benar ada di 10 teratas (Hit@10) | 1,00 | ≥ 0,95 |
| Urutan dokumen (MRR@10) | 0,88 | ≥ 0,70 |
| Bebas halusinasi | 0,98 | ≥ 0,90 |
| Kebenaran fakta | 0,98 | ≥ 0,80 |
| Menolak soal jebakan | 1,00 | ≥ 0,90 |
| Salah menolak | 0,00 | ≤ 0,10 |
| Waktu teks pertama muncul (p50 / p95) | 1,9 s / 5,0 s | – |
| Waktu jawaban selesai (p50 / p95) | 2,5 s / 6,5 s | – |
| Biaya menjawab | ±$0,0004 / pertanyaan | – |

Hasil run seluruh 123 soal: Hit@10 0,98, MRR@10 0,85, bebas halusinasi 0,99, kebenaran fakta 0,99, menolak soal
jebakan 0,95, waktu jawaban selesai p50 2,8 s. Angka bisa bergeser antar run karena model tidak deterministik.

## Keterbatasan yang diketahui

- **Kecepatan:** tidak semua jawaban di bawah 3 detik (±73% teks pertama, ±60% jawaban lengkap). Pertanyaan
  lanjutan lebih lambat karena di-rewrite oleh model.
- **Angka di tabel:** dengan `ANSWER_REASONING=minimal`, model kadang melewatkan angka di tabel; jawaban
  "tidak ditemukan" sudah diulang dengan `low`, tetapi belum sempurna. Bila akurasi lebih penting daripada
  kecepatan, set `ANSWER_REASONING=low`.
- **Index belum mutakhir:** `data/processed/` memuat 34 chunk (halaman Company Profile: visi-misi terbaru,
  biografi direksi) yang belum masuk `data/index/`. Jalankan `python -m bki_rag index` (biaya kecil) untuk
  memasukkannya.
- **Bahasa jawaban:** untuk pertanyaan pertama, bahasa ditentukan detektor lokal berbasis kata penanda
  (`ID_MARKERS`), bukan oleh model; pertanyaan campuran yang tidak memuat penanda bisa dijawab dalam bahasa yang
  tidak diinginkan.
- **Konten login:** BKI Rules & Regulations tidak bisa dijawab; pengguna diarahkan ke halaman login.
