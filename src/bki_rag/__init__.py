"""RAG chatbot over the public content of bki.co.id (PT Biro Klasifikasi Indonesia).

Pipeline: ingestion (crawl -> extract -> clean -> chunk) -> indexing -> retrieval -> generation.
Entry points: cli.py (`python -m bki_rag ...`), app/terminal.py, app/web/ (Streamlit).
All prompts live in prompts/; all settings in core/config.py.
"""
