"""Command line entry point: `python -m bki_rag <command>` (or the `bki-rag` script)."""
from __future__ import annotations

import argparse
import sys


# Baca perintah dari command line lalu jalankan (crawl, process, index, ask, chat, ...).
def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="bki_rag", description="RAG chatbot over bki.co.id")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("crawl", help="Stage 1: download raw pages, CMS data and PDFs")
    sub.add_parser("process", help="Stages 2-4: extract, clean, dedup, chunk")
    ix = sub.add_parser("index", help="Stage 5: contextualise, embed, build BM25")
    ix.add_argument("--no-context", action="store_true", help="skip contextual retrieval (baseline)")
    sub.add_parser("all", help="crawl + process + index")
    sub.add_parser("golden", help="Build the evaluation golden set")
    e = sub.add_parser("eval", help="Run retrieval (+ answer) evaluation")
    e.add_argument("--config", default="full",
                   help="vector, hybrid, hybrid_ctx, full, full_rerank, a comma list, or 'all'")
    e.add_argument("--answers", action="store_true", help="also generate answers and judge them")
    e.add_argument("--limit", type=int, default=None, help="evenly spread sample of N questions (cheaper)")
    a = sub.add_parser("ask", help="Ask one question and print the answer")
    a.add_argument("question", nargs="+")
    a.add_argument("--debug", action="store_true")
    c = sub.add_parser("chat", help="Interactive terminal chatbot")
    c.add_argument("--debug", action="store_true", help="show retrieved chunks")
    v = sub.add_parser("vectors", help="Look inside the vector index (free, no API calls)")
    v.add_argument("--chunk", help="chunk id to show (default: the first row)")
    v.add_argument("--query", help="embed this text and show the nearest chunks (tiny API cost)")
    v.add_argument("--dims", type=int, default=8, help="how many vector values to print")
    v.add_argument("--k", type=int, default=5, help="how many nearest chunks to show")
    v.add_argument("--export", help="also write full vectors of the first --rows chunks to this CSV file")
    v.add_argument("--rows", type=int, default=20)
    v.add_argument("--excel", help="write ALL chunks and vectors to this .xlsx file")
    args = p.parse_args()

    if args.cmd in ("crawl", "all"):
        from .ingestion import crawl
        crawl.run()
    if args.cmd in ("process", "all"):
        from .ingestion import pipeline
        pipeline.run()
    if args.cmd in ("index", "all"):
        from .indexing import pipeline as indexing
        indexing.run(contextualize=not getattr(args, "no_context", False))
    if args.cmd == "golden":
        from .evaluation.golden import build_golden
        build_golden()
    if args.cmd == "eval":
        from .evaluation.runner import run
        run(args.config, answers=args.answers, limit=args.limit)
    if args.cmd == "ask":
        from .app.terminal import ask_once
        ask_once(" ".join(args.question), debug=args.debug)
    if args.cmd == "chat":
        from .app.terminal import repl
        repl(debug=args.debug)
    if args.cmd == "vectors":
        from .indexing.inspect import show
        show(args.chunk, args.query, args.dims, args.k, args.export, args.rows, args.excel)
