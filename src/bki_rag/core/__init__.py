"""Shared foundation used by every stage.

  config.py  paths, model names and parameters (all overridable via .env / Streamlit Secrets)
  llm.py     OpenAI-compatible client: chat, streaming chat, JSON chat, embeddings, retries
  usage.py   token counters and cost (used by the evaluation)
  utils.py   JSONL IO, hashing, token counting, text normalisation, parallel map
"""
