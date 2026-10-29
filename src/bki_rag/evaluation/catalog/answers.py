"""Stage 2: metrik jawaban (bebas halusinasi, kebenaran fakta, penolakan)."""

ANSWERS = {
    "faithfulness": ("Bebas halusinasi (Faithful)", "Semua klaim jawaban didukung dokumen yang diambil.", 0.90, ">="),
    "answer_correctness": ("Kebenaran fakta", "Isi jawaban sesuai kunci jawaban acuan.", 0.80, ">="),
    "negative_rejection": ("Menolak soal jebakan", "Porsi soal di luar basis data yang ditolak.", 0.90, ">="),
    "false_refusal": ("Salah menolak", "Porsi soal yang bisa dijawab tapi ditolak.", 0.10, "<="),
}
