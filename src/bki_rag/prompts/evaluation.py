"""Prompts for drafting the golden test set and grading answers (gpt-5-nano)."""

GOLDEN_STYLES = {
    "short": ("Make it SHORT and casual (max 15 words), the way people type into a chat box. Do not quote document "
              "titles; just mention the topic (and the year only if the fact depends on it)."),
    "detailed": ("Make it self-contained and specific: name the topic explicitly (e.g. the service name, the report "
                 "year 'laporan tahunan 2024', the event or news topic)."),
}

GOLDEN_PROMPT = """You are building a test set for a chatbot about PT Biro Klasifikasi Indonesia (BKI), the Indonesian
ship classification society. Below is one passage from its website / reports.

<passage title="{title}" type="{doc_type}" date="{date}">
{text}
</passage>

Write ONE realistic question that a real user (ship owner, shipyard, job seeker, journalist, investor, student)
might ask, which this passage answers well, plus the reference answer.
Requirements:
- Write the question in {qlang}.
- {style}
- Never say "this passage/document/article".
- Paraphrase; do not copy long phrases from the passage. Prefer specific facts (numbers, names, dates,
  requirements, procedures) over vague summaries.
- If the passage is only navigation, a list of titles, an unreadable table, or has no meaningful fact, set suitable=false.
Return JSON: {{"suitable": true/false, "question": "...", "answer": "short reference answer in the question's language"}}"""

JUDGE_PROMPT = """Grade a chatbot answer about PT Biro Klasifikasi Indonesia (BKI).

Question: {question}
Answerable from knowledge base: {answerable}
Reference answer: {reference}

Retrieved sources given to the chatbot:
{sources}

Chatbot answer:
{answer}

Grade strictly and return JSON:
{{
  "refused": true if the answer states that the requested specific information is not available / not mentioned / not found in the sources or declines to answer (even if it mentions related context or alternative info), else false,
  "faithful": 1 if all factual claims made in the answer are supported by the retrieved sources (anti-hallucination), else 0,
  "correct": 1 if the answer correctly conveys the key facts from the reference answer (0.5 partial, 0 incorrect; for unanswerable questions 1 if it indicates the info is not available or declines, else 0),
  "note": "one short sentence"
}}"""
