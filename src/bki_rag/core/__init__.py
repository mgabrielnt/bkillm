"""Shared foundation used by every stage.

  config.py  paths, model names and parameters (all overridable via .env / Streamlit Secrets)
  llm.py     OpenAI-compatible client: chat, JSON chat, embeddings, parallel map with retries
  utils.py   JSONL IO, hashing, token counting, text normalisation
"""
