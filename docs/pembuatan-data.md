# Pembuatan data: dari situs sampai index

Chatbot hanya membaca `data/index/`. Dokumen ini menjelaskan bagaimana folder itu dibuat. Anda hanya perlu
menjalankannya kalau isi situs bki.co.id berubah.

```
crawl ──► extract ──► clean ──► chunk ──► index
(Tahap 1)  (Tahap 2)  (Tahap 3) (Tahap 4) (Tahap 5)
data/raw/                data/processed/        data/index/
```

| Perintah | Tahap | Biaya |
|---|---|---|
| `python -m bki_rag crawl` | 1 | gratis (±3 menit, 1 request/detik) |
| `python -m bki_rag process` | 2–4 | gratis |
| `python -m bki_rag index` | 5 | berbayar, hanya untuk chunk baru/berubah |
| `python -m bki_rag all` | 1–5 | gabungan di atas |

Setiap tahap bisa diulang tanpa mengulang tahap sebelumnya: `process` membaca `data/raw/`, `index` membaca
`data/processed/chunks.jsonl`.

## Tahap 1. Crawl ([ingestion/crawl/](../src/bki_rag/ingestion/crawl/__init__.py))

Menyimpan respons mentah apa adanya, plus satu baris manifest per URL (`data/raw/manifest.jsonl`).

| File | Tugas |
|---|---|
| `fetcher.py` | Client HTTP sopan: User-Agent jujur, jeda 1 detik, ulang dengan backoff bila 5xx atau ditolak WAF. Tidak mengakali WAF |
| `cms.py` | Koleksi CMS Strapi publik (`cms.bki.co.id/api`): berita, artikel, event, halaman ESG (EN+ID), lowongan, daftar laporan → `data/raw/cms/*.json` |
| `site.py` | Halaman statis dari `sitemap.xml` → `data/raw/site/*.html`, plus kamus terjemahan Indonesia `locale_id.json`. Halaman yang mengarah ke `/login` dicatat `auth_required` dan tidak pernah di-login |
| `pdfs.py` | Laporan tahunan/keberlanjutan dan PDF yang ditautkan halaman → `data/raw/pdf/` (satu kali per URL) |

Urutannya wajib cms → site → pdfs, karena `pdfs.py` membaca hasil dua langkah sebelumnya.
Jumlah laporan diatur `ANNUAL_REPORT_YEARS` dan `SUSTAINABILITY_REPORT_LIMIT` di `config.py`.

## Tahap 2. Ekstraksi ([ingestion/extract/](../src/bki_rag/ingestion/extract/__init__.py))

Mengubah file mentah menjadi dokumen Markdown dengan metadata (`url`, `title`, `lang`, `doc_type`, ...).

| File | Tugas |
|---|---|
| `rsc.py` | Membongkar payload React Server Components yang disisipkan Next.js di HTML; mencari kamus terjemahan Inggris |
| `rsc_text.py` | Teks yang terlihat di pohon elemen halaman |
| `i18n.py` | Menyusun ulang namespace kamus jadi Markdown (judul dulu, baru teksnya) |
| `urls.py` | URL halaman untuk setiap namespace (untuk sitasi) dan jenis dokumen dari URL |
| `pages.py` | Dokumen halaman statis (Inggris + Indonesia) |
| `tiptap.py` | Rich text CMS (TipTap / blok Strapi) → Markdown |
| `cms.py` | Dokumen berita, artikel, event, ESG, lowongan |
| `pdf.py` | Dokumen PDF, satu bagian per halaman (agar sitasi memuat nomor halaman); hasil parse di-cache di `data/cache/` |

## Tahap 3. Pembersihan ([ingestion/clean/](../src/bki_rag/ingestion/clean/__init__.py))

Urutan: filter baris boilerplate dua bahasa → filter frekuensi lintas dokumen (menu, footer, alamat kantor yang
berulang di banyak halaman; PDF: header/footer per dokumen) → normalisasi Unicode → buang duplikat persis dan
hampir-sama (MinHash, Jaccard ≥ 0,8; URL duplikat disimpan sebagai `aliases`) → buang dokumen di bawah 50 kata.
Laporannya ada di `data/processed/cleaning_report.txt`.

## Tahap 4. Chunking ([ingestion/chunk/](../src/bki_rag/ingestion/chunk/__init__.py))

Dipotong mengikuti struktur dokumen, bukan jumlah karakter:

- Dokumen dipecah per paragraf; judul (`#`, `##`, ...) dilacak sebagai jalur bagian.
- Paragraf digabung sampai ±500 token (`CHUNK_TARGET_TOKENS`), maksimal 800 (`CHUNK_MAX_TOKENS`).
- Dokumen web pendek (≤ 800 token) tetap satu chunk. Chunk baru dimulai saat bagian berganti jika chunk
  sekarang sudah lebih dari setengah penuh. Overlap ±10% bila pemotongan jatuh di tengah bagian.
- Paragraf terlalu panjang dipecah: tabel per baris (header diulang), teks per kalimat.
- Setiap chunk diawali breadcrumb `Judul > Bagian > Subbagian`.

Hasilnya `data/processed/chunks.jsonl`. Isi satu baris:

| Field | Arti |
|---|---|
| `chunk_id`, `doc_id`, `chunk_index` | Identitas chunk dan urutannya di dokumen |
| `url`, `aliases`, `group_id` | Sumber sitasi; `group_id` menyatukan versi EN dan ID dari item yang sama |
| `title`, `section_path`, `doc_type`, `lang`, `published_at` | Metadata |
| `page_from`, `page_to` | Rentang halaman PDF (`null` untuk halaman web) |
| `text`, `tokens`, `content_hash` | Isi (dengan breadcrumb), jumlah token, hash untuk cache dan deteksi perubahan |

## Tahap 5. Indexing ([indexing/](../src/bki_rag/indexing/__init__.py))

1. **`contextualize.py`**: model menulis 1–3 kalimat konteks dua bahasa untuk tiap chunk ("bagian ini ada di
   halaman X yang membahas Y"). Hasilnya di-cache per `content_hash` di `data/cache/context.jsonl`, sehingga
   run ulang hanya membayar chunk baru.
2. **`store.py`**: teks yang di-index adalah `konteks + isi chunk` (`search_text`). Embedding dibuat dengan
   `text-embedding-3-large` dan di-cache per hash teks di `data/cache/emb_<model>/store.npz`. BM25 dibuat dari
   teks yang sama.
3. Hasil tulis ke `data/index/`: `chunks.jsonl`, `embeddings.npy`, `bm25/`, `meta.json`.

`embeddings.npy` ditulis ulang dari nol setiap kali, sedangkan cache embedding hanya bertambah, jadi cache
biasanya berisi vektor lama yang tidak terpakai. Aman dibiarkan; menghapusnya hanya membuat run berikutnya
membayar ulang.

Memeriksa isi index (gratis, tanpa API): `python -m bki_rag vectors` (lihat `--help` untuk `--chunk`, `--query`,
`--export`, `--excel`).

## Catatan penting

- Jangan hapus `data/raw/` dan `data/cache/` di lokal: isinya membuat proses ulang gratis.
- Mengganti `EMBED_MODEL` berarti seluruh index harus dibangun ulang, karena vektor pertanyaan harus berasal dari
  model yang sama dengan vektor chunk.
- Mengubah prompt konteks (`prompts/indexing.py`) tidak otomatis membuat ulang konteks lama, karena cache memakai
  hash chunk, bukan hash prompt. Hapus `data/cache/context.jsonl` bila ingin membuatnya ulang (berbayar).
