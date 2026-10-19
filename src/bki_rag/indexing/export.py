"""Export the vector index to files people can open (`python -m bki_rag vectors --export / --excel`)."""
from __future__ import annotations

import csv

from .store import Index


def to_csv(ix: Index, path: str, rows: int) -> None:
    """Write the first `rows` chunks and their full vectors to CSV."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["chunk_id", "title", "url"] + [f"d{j}" for j in range(ix.emb.shape[1])])
        for c, vec in zip(ix.chunks[:rows], ix.emb[:rows]):
            w.writerow([c["chunk_id"], c["title"], c["url"]] + [f"{x:.6f}" for x in vec])
    print(f"exported {min(rows, len(ix.chunks))} rows to {path}")


def to_excel(ix: Index, path: str) -> None:
    """Write ALL chunks to an .xlsx: sheet "chunks" (what each row is) and sheet "vectors" (the numbers)."""
    import xlsxwriter  # pip install xlsxwriter; only needed for this export

    wb = xlsxwriter.Workbook(path, {"constant_memory": True})
    info = wb.add_worksheet("chunks")
    info.write_row(0, 0, ["row", "chunk_id", "title", "url", "doc_type", "lang", "pages", "text (first 300 chars)"])
    for i, c in enumerate(ix.chunks, 1):
        pages = f"{c['page_from']}-{c['page_to']}" if c.get("page_from") else ""
        info.write_row(i, 0, [i, c["chunk_id"], c["title"], c["url"], c["doc_type"], c["lang"], pages,
                              c["text"][:300]])
    vec = wb.add_worksheet("vectors")
    vec.write_row(0, 0, ["row", "chunk_id"] + [f"d{j}" for j in range(ix.emb.shape[1])])
    for i, (c, v) in enumerate(zip(ix.chunks, ix.emb), 1):
        vec.write_row(i, 0, [i, c["chunk_id"]] + [round(float(x), 6) for x in v])
    wb.close()
    print(f"exported {len(ix.chunks)} chunks x {ix.emb.shape[1]} dims to {path}")
