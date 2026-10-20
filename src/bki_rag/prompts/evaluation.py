"""Prompts for drafting the golden test set and grading answers (gpt-5-nano).

Placeholders in {braces} are filled with str.format(); literal JSON braces are doubled.
"""

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

JUDGE_PROMPT = """You grade a chatbot answer about PT Biro Klasifikasi Indonesia (BKI).

Question: {question}
Answerable from the knowledge base: {answerable}
Reference answer: {reference}

Sources given to the chatbot:
{sources}

Chatbot answer:
{answer}

Grade strictly and return JSON:
{{"correct": 1 if the answer conveys the reference answer's key facts (0.5 if partially, 0 if wrong/missing;
             for unanswerable questions 1 if it clearly says the information is not available / declines, else 0),
  "faithful": 1 if every BKI-specific claim in the answer is supported by the sources (text, context, title
              or date all count as support), else 0,
  "cited": 1 if the answer cites [n] sources that support its main claims (1 also for a correct refusal without citations), else 0,
  "refused": true if the answer says the information was not found / declines, else false,
  "same_language": true if the answer is in the same language as the question,
  "note": "one short sentence"}}"""
