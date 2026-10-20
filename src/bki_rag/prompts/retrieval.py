"""Prompt for query rewriting (gpt-5-nano).

Placeholders in {braces} are filled with str.format(); literal JSON braces are doubled.
"""

REWRITE_PROMPT = """You rewrite user questions for searching the website of PT Biro Klasifikasi Indonesia (BKI), the
Indonesian ship classification society. The corpus mixes English and Indonesian pages, news, ESG pages and annual reports.

Conversation so far (may be empty):
{history}

Latest user message: {question}

Return JSON:
{{"standalone": "the latest message as a self-contained question (resolve pronouns like 'itu', 'that', 'yang tadi' from the conversation), same language as the user",
  "en": "the standalone question in English",
  "id": "the standalone question in Indonesian",
  "keywords": "5-12 exact search terms in both languages: names, acronyms, regulation numbers, synonyms (e.g. 'load line garis muat ICLL')",
  "lang": "language of the latest user message: 'id' for Indonesian (including casual/slang), 'en' for English"}}"""
