# Alur satu pertanyaan

Dokumen ini menjelaskan apa yang dijalankan kode dari aplikasi dibuka sampai jawaban tampil. Kalau Anda ingin
mengubah perilaku chatbot, mulailah dari sini untuk menemukan file yang tepat.

Contoh yang dipakai: *"Apa saja yang diperiksa saat Port State Control?"*

## Gambaran: dua waktu yang berbeda

1. **Saat aplikasi dinyalakan (sekali):** empat file di `data/index/` dibaca ke memori.
2. **Setiap pertanyaan:** program mencari di memori, memanggil API OpenAI, lalu menampilkan hasilnya.

Analogi perpustakaan: `chunks.jsonl` adalah isi buku (kartu berisi paragraf), `embeddings.npy` adalah katalog
berdasarkan **makna**, `bm25/` adalah katalog berdasarkan **kata**, `meta.json` adalah label katalog.

## A. Saat aplikasi dinyalakan

```
streamlit_app.py
 └─ app/web/page.py  main()
     └─ _load()                          @st.cache_resource: hanya sekali per server
         └─ generation/answer.py  RAG()
             └─ retrieval/retriever.py  Retriever()
                 └─ indexing/store.py  Index()      ← di sini file dibaca
```

`Index.__init__` ([indexing/store.py](../src/bki_rag/indexing/store.py)) memuat:

```python
self.chunks = list(read_jsonl(path / "chunks.jsonl"))   # teks + metadata tiap chunk
self.emb    = np.load(path / "embeddings.npy")           # matriks (jumlah chunk × 3072)
self.bm25   = bm25s.BM25.load(str(path / "bm25"))        # index kata kunci
self.meta   = json.loads((path / "meta.json").read_text())
```

**Aturan penting:** baris ke-N di `chunks.jsonl` dan baris ke-N di `embeddings.npy` adalah chunk yang sama.
Itulah yang menghubungkan vektor dengan teksnya.

`Retriever()` juga memanaskan detektor bahasa (`langdetect`) supaya pertanyaan pertama tidak tertunda ±1,3 detik.

## B. Setiap pertanyaan

### B1. `app/web/page.py`: terima pertanyaan, cek batas

```python
warning = session_block(ss.asked, ss.last_ask)      # maks 30/sesi, jeda 3 detik
if warning is None and not limiter.try_consume():   # maks 200/hari, dicatat di data/usage/
    warning = "Batas pertanyaan harian ..."
...
_ask(rag, question)   # → rag.answer(question, history, on_text=show_text)
```

Kalau batas terlampaui, tidak ada API yang dipanggil. `history` berisi 6 pesan terakhir. `on_text` menerima
potongan jawaban selagi ditulis (streaming); nomor sitasi mentah disembunyikan lewat `hide_citations`.

### B2. `generation/answer.py`: `RAG.answer()` mengatur urutan

```python
page = match_restricted(question)                 # B3
if page: return self._restricted(...)             # link login, selesai, 0 API
found = self.retriever.search(question, history)  # B4–B8
text_raw, t_first = reply(_messages(...), on_text)  # B9–B10
text, sources = renumber_citations(text_raw, chunks)  # B11
```

### B3. `retrieval/restricted.py`: topik di balik login?

Pertanyaan yang memuat kata seperti *rules, regulasi, peraturan, aturan, pedoman, guidelines* langsung dibalas
dengan link login BKI Rules & Regulations. Tanpa pencarian dan tanpa API. Contoh kita tidak cocok, jadi lanjut.

### B4. `retrieval/retriever.py`: `Retriever.search()`

```python
q = rewrite_query(question, history) if history or C.REWRITE_FIRST_QUESTION else plain_query(question)
variants = [q["standalone"], q["en"], q["id"]]    # tanpa duplikat
vectors  = embed(variants, ..., timeout=C.QUERY_EMBED_TIMEOUT_S)
ranked   = [ix.vector_search(v, 50) for v in vectors] + [ix.bm25_search(f"{v} {kw}", 50) for v in variants]
candidates = [ix.chunks[i] for i in reciprocal_rank_fusion(ranked)]
return {"query": q, "chunks": candidates[:10], "ranking": candidates, "timing": {...}}
```

### B5. Rewrite pertanyaan ([retrieval/query.py](../src/bki_rag/retrieval/query.py))

| Kondisi | Yang dipakai | API? |
|---|---|---|
| Pertanyaan pertama (tanpa riwayat) | `plain_query`: pertanyaan apa adanya + bahasa dari `langdetect` | tidak |
| Pertanyaan lanjutan (ada riwayat) | `rewrite_query`: model menulis ulang | **ya** |

`rewrite_query` meminta model (prompt di [prompts/retrieval.py](../src/bki_rag/prompts/retrieval.py)) membuat JSON:

```json
{"standalone": "Apa saja yang diperiksa saat Port State Control?",
 "en": "What is inspected during Port State Control?",
 "id": "Apa saja yang diperiksa saat Port State Control?",
 "keywords": "Port State Control PSC kontrol negara pelabuhan SOLAS MARPOL MLC inspeksi",
 "lang": "id"}
```

Tujuannya: (1) mengubah "kalau yang itu?" menjadi pertanyaan lengkap, (2) mencari di dua bahasa karena isi
situs campuran EN/ID, (3) menambah kata kunci untuk BM25. `REWRITE_FIRST_QUESTION=1` memaksa rewrite juga di
pertanyaan pertama.

### B6. Embedding ([core/llm.py](../src/bki_rag/core/llm.py) `embed`)

Semua versi pertanyaan dikirim dalam satu request ke `text-embedding-3-large` (3072 angka per teks, dinormalisasi).
Model harus sama dengan pembuat index. Batas waktu `QUERY_EMBED_TIMEOUT_S` (2 detik) membuat permintaan yang
tersendat diulang cepat.

### B7. Dua cara mencari (lokal, di memori)

- **`vector_search`** (makna): `self.emb @ qvec` membandingkan vektor pertanyaan dengan **semua** vektor chunk
  sekaligus, lalu mengambil 50 skor tertinggi. Menemukan chunk yang maknanya sama walau katanya beda.
- **`bm25_search`** (kata): pertanyaan + kata kunci dipecah jadi kata, stopword dibuang, BM25 memberi skor
  tinggi pada chunk yang memuat kata langka yang sama. Kuat untuk istilah, singkatan, dan nomor regulasi.

### B8. `reciprocal_rank_fusion`: menggabungkan semua daftar

Skor vektor dan BM25 tidak sebanding, jadi RRF hanya memakai **posisi**: tiap chunk mendapat `1 / (60 + posisi)`
dari setiap daftar tempat ia muncul, lalu dijumlahkan. 10 teratas dikirim ke model.

### B9. `generation/sources.py`: menyiapkan bahan untuk model

`build_context` membungkus 10 chunk menjadi XML `<source id="1" title=... url=... type=... status=...>`.
Atribut `status` memberi tahu seberapa baru informasinya: *current live website page*, *dated item published
...*, atau *report covering year ...*. System prompt memakainya untuk memilih sumber yang tepat.

### B10. `generation/reply.py`: model menjawab

```python
ask_model(messages, ANSWER_REASONING, on_text, drop_refusal=True)   # cepat (minimal)
→ jika hasilnya penolakan ("Maaf, ... tidak ditemukan"): jawaban ditahan,
  ask_model(messages, RETRY_REASONING, on_text, drop_refusal=False)  # teliti (low)
```

- 60 huruf pertama ditahan sebelum tampil supaya penolakan palsu tidak sempat terlihat di layar.
- Model cepat kadang melewatkan angka di tabel; karena itu penolakan diulang dengan `low`.
- Aturan jawaban ada di [prompts/answer.py](../src/bki_rag/prompts/answer.py): hanya dari sumber, wajib sitasi `[n]`,
  bahasa penanya, tolak dengan sopan bila tidak ada.

### B11. `generation/citations.py`: rapikan sitasi

Model mengutip dengan posisi sumber (`[4][9]`). `renumber_citations` menomori ulang 1, 2, 3 sesuai urutan
muncul, menyatukan chunk dari halaman yang sama, dan membuat daftar sumber dengan nomor yang persis sama.

### B12. Tampil di layar

`page.py` menyimpan jawaban dan sumber di riwayat sesi, lalu `views.show_message` menampilkannya sebagai
Markdown tanpa HTML, dan `source_links` menulis daftar sumber ("Sumber" atau "Sources" sesuai bahasa).
Error apa pun diubah `errors.friendly_error` menjadi pesan aman tanpa membocorkan API key.

## Panggilan API per pertanyaan

| Jenis pertanyaan | Panggilan |
|---|---|
| Rules / regulasi | 0 |
| Pertama (tanpa riwayat) | 1 embedding + 1 chat (jawaban); +1 chat bila jawaban awal berupa penolakan |
| Lanjutan (ada riwayat) | 1 chat (rewrite) + 1 embedding + 1 chat (jawaban); +1 chat bila ditolak dulu |

Semua panggilan melewati [core/llm.py](../src/bki_rag/core/llm.py), satu-satunya file yang memanggil OpenAI.

## Peta singkat

```
page._ask ─► RAG.answer
   ├─ restricted.match_restricted        topik terkunci? → link login
   ├─ retriever.search
   │    ├─ query.plain_query / rewrite_query
   │    ├─ llm.embed
   │    ├─ store.vector_search / bm25_search   (lokal)
   │    └─ reciprocal_rank_fusion → 10 chunk
   ├─ sources.build_context
   ├─ reply.reply (streaming + cek ulang penolakan)
   └─ citations.renumber_citations
```
