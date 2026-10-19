"""Every LLM prompt, one module per pipeline stage. Edit prompts here (prompt engineering).

Modules:
  indexing.py    GLOSSARY, CONTEXT_PROMPT
  retrieval.py   REWRITE_PROMPT, RERANK_PROMPT
  answer.py      ANSWER_SYSTEM_PROMPT, ANSWER_USER_PROMPT
  evaluation.py  GOLDEN_STYLES, GOLDEN_PROMPT, JUDGE_PROMPT
"""
from .indexing import GLOSSARY, CONTEXT_PROMPT
from .retrieval import REWRITE_PROMPT, RERANK_PROMPT
from .answer import ANSWER_SYSTEM_PROMPT, ANSWER_USER_PROMPT
from .evaluation import GOLDEN_STYLES, GOLDEN_PROMPT, JUDGE_PROMPT

__all__ = ["GLOSSARY", "CONTEXT_PROMPT", "REWRITE_PROMPT", "RERANK_PROMPT", "ANSWER_SYSTEM_PROMPT", "ANSWER_USER_PROMPT", "GOLDEN_STYLES", "GOLDEN_PROMPT", "JUDGE_PROMPT"]
