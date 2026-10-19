"""Terminal chatbot: `python -m bki_rag chat` (interactive) and `python -m bki_rag ask "..."` (one question)."""
from __future__ import annotations

from ..core import config as C
from ..generation.answer import RAG

HELP = "Perintah: /reset (hapus riwayat), /debug (tampilkan chunk), /exit (keluar)"


def _print_result(res: dict, debug: bool) -> None:
    """Print one answer with its numbered sources (and the retrieved chunks in debug mode)."""
    print(f"\nBot: {res['answer']}\n")
    if res["sources"]:
        english = res["query"].get("lang") == "en"
        label, page = ("Sources", "p.") if english else ("Sumber", "hal.")
        print(f"{label}:")
        for s in res["sources"]:
            p = s["pages"]
            pages = "" if not p else f" ({page} {p[0]})" if p[0] == p[1] else f" ({page} {p[0]}-{p[1]})"
            print(f"  [{s['n']}] {s['title']}{pages}\n      {s['url']}")
    if debug:
        print(f"\n[debug] query: {res['query']}")
        for i, c in enumerate(res["chunks"], 1):
            print(f"[debug] {i:2d}. {c['chunk_id']} | {c['doc_type']} | {c['lang']} | {c['title'][:70]}")
    print(f"[{res['timing']['total_s']}s, retrieval {res['timing']['retrieval_s']}s]\n")


def ask_once(question: str, debug: bool = False) -> None:
    """Answer a single question from the command line (`ask`)."""
    _print_result(RAG().answer(question), debug)


def repl(debug: bool = False) -> None:
    """Interactive chat loop with history and /reset, /debug, /exit (`chat`)."""
    rag = RAG()
    history: list[dict] = []
    print(f"BKI RAG chatbot ({C.CHAT_MODEL} + {rag.retriever.index.meta['embed_model']}, "
          f"{len(rag.retriever.index.chunks)} chunks). {HELP}\n")
    while True:
        try:
            q = input("Anda: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q:
            continue
        if q in ("/exit", "/quit", "exit", "quit"):
            break
        if q == "/reset":
            history.clear()
            print("(riwayat dihapus)\n")
            continue
        if q == "/debug":
            debug = not debug
            print(f"(debug {'on' if debug else 'off'})\n")
            continue
        try:
            res = rag.answer(q, history)
        except Exception as e:  # keep the session alive on API errors
            print(f"[error] {e}\n")
            continue
        _print_result(res, debug)
        history += [{"role": "user", "content": q}, {"role": "assistant", "content": res["answer"]}]
        history = history[-8:]
