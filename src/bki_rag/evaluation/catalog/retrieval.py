"""Stage 1: temu dokumen (Hit@10, MRR@10)."""

RETRIEVAL = {
    "hit@10": ("Dokumen ditemukan (Hit@10)", "Dokumen/link benar masuk ke 10 hasil teratas.", 0.95, ">="),
    "mrr@10": ("Urutan dokumen (MRR@10)", "Rata-rata 1/peringkat dokumen benar di 10 teratas.", 0.70, ">="),
}
