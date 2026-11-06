# Panduan pengembangan

Untuk siapa pun yang melanjutkan proyek ini. Baca [README.md](../README.md) dulu untuk gambaran dan cara
menjalankan, lalu [alur-pertanyaan.md](alur-pertanyaan.md) untuk memahami kode.

## Konvensi kode

- **Satu tugas per file, file pendek** (sekitar 100 baris). Kalau file membesar, pecah (contoh: `generation/reply.py`
  dipisah dari `answer.py`, `evaluation/answer_eval.py`, `report.py`, dan `guard.py` dari `runner.py`).
- **Setiap folder punya `__init__.py`** dengan docstring yang menjelaskan isinya. Perbarui saat menambah file.
- **Setiap fungsi dan class diberi komentar `#` Bahasa Indonesia tepat di atas `def`/`class`**, satu atau dua
  baris tentang *apa yang dilakukan*. Docstring modul memakai Bahasa Inggris.
- **Semua prompt ada di [prompts/](../src/bki_rag/prompts/)**, satu file per tahap. Jangan menulis prompt di
  tempat lain.
- **Semua pengaturan ada di [core/config.py](../src/bki_rag/core/config.py)**, dibaca lewat `_env(...)` agar bisa
  diubah dari `.env` atau Secrets. Tambahkan juga ke [.env.example](../.env.example) dan tabel di README.
- **Hanya [core/llm.py](../src/bki_rag/core/llm.py) yang memanggil OpenAI.** Modul lain memakai `chat`,
  `chat_stream`, `chat_json`, atau `embed`.
- **Kode UI tidak berisi logika RAG.** UI hanya memanggil `RAG().answer(...)` (lihat `app/web/page.py`).
- Pemeriksaan gaya yang dipakai: `ruff check src --select F,E731,E9` harus bersih.

## Peta: ingin mengubah apa?

| Ingin mengubah | Buka |
|---|---|
| Aturan menjawab, nada, bahasa jawaban | `prompts/answer.py` |
| Cara pertanyaan ditulis ulang | `prompts/retrieval.py`, `retrieval/query.py` |
| Jumlah chunk ke model, jumlah kandidat | `TOP_K`, `CANDIDATES_PER_QUERY` di `core/config.py` |
| Cara menggabungkan hasil pencarian | `retrieval/retriever.py` (`reciprocal_rank_fusion`) |
| Format sumber yang dilihat model | `generation/sources.py` |
| Sitasi dan daftar sumber | `generation/citations.py` |
| Kecepatan vs ketelitian jawaban | `ANSWER_REASONING`, `RETRY_REASONING`, `generation/reply.py` |
| Topik yang diarahkan ke halaman login | `retrieval/restricted.py` |
| Tampilan web, batas pemakaian | `app/web/` |
| Cara memotong dokumen jadi chunk | `ingestion/chunk/` |
| Pembersihan boilerplate | `ingestion/clean/filters.py` |
| Sumber data baru (halaman, koleksi CMS, PDF) | `ingestion/crawl/` lalu `ingestion/extract/` |
| Prompt konteks chunk | `prompts/indexing.py` |

## Pola yang perlu dipahami

- **Index dibaca sekali** saat aplikasi mulai (`@st.cache_resource` di `page.py`). Mengganti isi `data/index/`
  berarti aplikasi harus dimulai ulang.
- **Mengubah prompt jawaban tidak butuh membangun ulang index.** Mengubah chunking, pembersihan, prompt konteks,
  atau `EMBED_MODEL` membutuhkan `process` lalu `index` (dan konteks lama di cache tidak otomatis dibuat ulang).
- **Hasil pencarian dan jawaban tidak deterministik.** Evaluasi dua kali bisa memberi angka sedikit berbeda;
  bandingkan pengaturan pada soal yang sama dan jangan menyimpulkan dari selisih kecil.
- **Penolakan "tidak ditemukan" dideteksi dengan pola teks** (`REFUSAL` di `generation/reply.py`). Kalau kalimat
  penolakan di `prompts/answer.py` diubah, ubah pola itu juga.
- **Bahasa jawaban pertanyaan pertama ditentukan secara lokal** (`detect_lang` di `retrieval/query.py`): kata
  penanda Indonesia (apa, yang, berapa, ...) menang atas `langdetect`, yang sering salah menebak pertanyaan pendek
  berisi istilah Inggris. Bila ada pertanyaan yang dijawab dalam bahasa yang salah, tambahkan kata penandanya di
  `ID_MARKERS`. Pertanyaan lanjutan memakai bahasa hasil rewrite model.
- **Jawaban streaming dan sitasi:** teks sementara menyembunyikan nomor sitasi (`hide_citations`); nomor final
  baru ada setelah `renumber_citations`.

## Evaluasi

```powershell
python -m bki_rag eval --answers --limit 30 --workers 1
```

- `--answers`: ikut menjawab dan dinilai juri (berbayar). Tanpa itu hanya mengukur pencarian (Hit@10, MRR@10).
- `--limit N`: sampel N soal yang tersebar rata, supaya murah.
- `--workers 1`: soal dijawab satu per satu agar **waktu respons akurat**. Dengan 8 pekerja paralel (bawaan)
  waktu menjadi lebih lambat karena antre di API.
- `--rejudge <file>`: menilai ulang jawaban yang belum dinilai dari run sebelumnya, tanpa menjawab ulang.

Hasil ditulis ke `data/eval/results/` dengan awalan stempel waktu:

| File | Isi |
|---|---|
| `<stempel>_summary.json` | Metrik, waktu p50/p95 tiap tahap, biaya, dan pengaturan yang dipakai |
| `<stempel>_answers_details.jsonl` | Per soal: jawaban, sumber, nilai juri, waktu |
| `<stempel>_retrieval_misses.jsonl` | Soal yang dokumen benarnya tidak ada di 10 teratas |

Metrik dan targetnya didefinisikan di [evaluation/catalog/](../src/bki_rag/evaluation/catalog/__init__.py).
Cara membaca: Hit@10 dan MRR@10 mengukur **pencarian**; faithfulness (tanpa halusinasi), kebenaran fakta,
menolak soal jebakan, dan salah menolak mengukur **jawaban**, dinilai oleh `gpt-5-nano` sebagai juri.

Catatan tentang juri: nomor sitasi dibuang dari jawaban sebelum dinilai, karena nomornya sudah diurut ulang dan
tidak cocok dengan daftar sumber yang dilihat juri. Juri sendiri bisa keliru, jadi periksa soal yang gagal di
`_answers_details.jsonl` sebelum menyimpulkan.

Membuat ulang golden set: `python -m bki_rag golden` (berbayar, **menimpa** `data/eval/golden.jsonl`; salin dulu
bila ingin menyimpan versi lama). Soal jebakan ada di daftar `UNANSWERABLE` di `evaluation/golden.py`.

## Mengukur kecepatan

`RAG.answer()` mengembalikan `timing`: `rewrite_s`, `embed_s`, `search_s`, `retrieval_s`, `first_text_s`,
`answer_s`, `total_s`. Evaluasi mencetak p50 dan p95 tiap tahap. Tahap yang paling lama adalah panggilan API
(embedding sekitar 0,7 detik, jawaban 1,5–5 detik); pencarian lokal hanya beberapa milidetik, jadi tidak perlu
database vektor untuk ukuran index sekarang (±1.800 chunk).

## Pemecahan masalah

| Gejala | Penyebab dan solusi |
|---|---|
| "Layanan belum terkonfigurasi: OPENAI_API_KEY" | Isi `OPENAI_API_KEY` di `.env` atau Secrets |
| "Kuota atau saldo layanan AI sedang habis" | Saldo/batas penyedia API habis; isi atau naikkan batas |
| "Model AI yang diatur tidak tersedia" | Periksa `LLM_MODEL` / `EMBED_MODEL` dan `OPENAI_BASE_URL` |
| Hasil pencarian aneh setelah ganti `EMBED_MODEL` | Vektor pertanyaan dan chunk harus dari model yang sama; jalankan `index` ulang |
| Jawaban "tidak ditemukan" padahal datanya ada | Cek `python -m bki_rag ask "..." --debug` untuk melihat chunk yang terambil; bila chunk benar ada, coba `ANSWER_REASONING=low` |
| Soal evaluasi gagal dengan "ContentPolicyViolation" | Penyaring konten gateway menolak prompt tertentu; soal itu dicatat sebagai error, bukan dijawab |
| `Batas pertanyaan harian tercapai` | Hitungan di `data/usage/daily_questions.json`; naikkan `DAILY_QUESTION_LIMIT` atau hapus file itu |
| Informasi terbaru situs tidak muncul | Index belum dibangun ulang; lihat [pembuatan-data.md](pembuatan-data.md) |

## Alur kerja perubahan yang disarankan

1. Ubah kode atau prompt.
2. `ruff check src --select F,E731,E9` dan jalankan `python -m bki_rag ask "..."` untuk uji cepat.
3. Bandingkan dengan `eval --answers --limit 60 --workers 1` sebelum dan sesudah, pada soal yang sama.
4. Perbarui README / dokumen ini bila perilaku atau pengaturan berubah.
5. Commit dengan pesan yang menjelaskan *kenapa*, bukan hanya apa.
