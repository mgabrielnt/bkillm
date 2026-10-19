"""Prompt for contextual retrieval while indexing (CONTEXT_MODEL), plus the domain glossary.

Placeholders in {braces} are filled with str.format(); literal JSON braces are doubled.
"""

GLOSSARY = ("BKI = Biro Klasifikasi Indonesia (Indonesian Classification Bureau); SOLAS = Safety of Life at Sea; "
            "MARPOL = marine pollution convention; ISM = International Safety Management; ISPS = International Ship and "
            "Port Facility Security; MLC = Maritime Labour Convention; GT = gross tonnage; PSC = Port State Control; "
            "BWM = ballast water management; ICLL = load line convention (garis muat); IACS = International Association "
            "of Classification Societies; TICCS = Testing, Inspection, Certification, Classification and Statutory; "
            "IDSurvey = state-owned survey services holding led by BKI.")

# Document first, chunk last: identical prefixes per document hit OpenAI's automatic prompt cache.
CONTEXT_PROMPT = """<document title="{title}" url="{url}" type="{doc_type}">
{document}
</document>

Here is a chunk from that document:
<chunk>
{chunk}
</chunk>

Glossary: {glossary}

Write 1-3 sentences (max ~80 words) that situate this chunk within the document to improve search retrieval:
what the document is, which section/topic this chunk covers, and the key entities, dates or numbers.
Include key terms in BOTH English and Indonesian (e.g. "load line / garis muat", "annual report / laporan tahunan").
Answer with the context only, no preamble."""
