"""
band.py

Shared rules for the Core Competencies band -- the block of pipe-separated
keywords that sits between the summary and Professional Experience.

It lives in its own module because both ends of the pipeline need the same
rules and they must not drift:

    resume_tailor.py     cleans the selection before it is written to JSON
    resume_generator.py  lays the rows out in the .docx

The band is the densest keyword real estate on the page, which makes it the
easiest place to look padded.  Three things went wrong on the Attensi resume:
the skills row carried a "Technical:" label the rest of the band did not have,
it repeated ten terms already printed two lines above it, and it was long
enough to wrap -- and because the band inherits the template's JUSTIFIED
Normal style, a wrapped row gets its word spacing stretched edge to edge.
"""

# Words that carry no meaning on their own when comparing a skill to a
# competency.  "Project Management" and "Program & Project Delivery" are the
# same claim; the shared word that proves it is "project", not "management".
STOPWORDS = {"management", "managing", "and", "the", "of", "in", "&"}

COMPETENCIES_PER_LINE = 3
CHARS_PER_LINE        = 92   # keeps a row on one rendered line at 10.5pt / 7in
MAX_SKILL_TERMS       = 10


def tokens(phrase):
    """Significant words in a band entry, lowercased and punctuation-free."""
    cleaned = "".join(c if c.isalnum() or c.isspace() else " " for c in phrase.lower())
    return {w for w in cleaned.split() if w and w not in STOPWORDS}


def dedupe_skills(skills, competencies):
    """
    Drop skills already claimed by the competency rows above them.

    A skill is a duplicate when all of its significant words appear in a single
    competency: "Agile" inside "Agile & Waterfall Delivery", "Project
    Management" inside "Program & Project Delivery", "Risk Management" inside
    "Risk & Compliance".  String equality would catch only one of those three,
    which is how the Attensi resume shipped Stakeholder Management twice.

    Returns (kept, dropped).
    """
    comp_tokens = [tokens(c) for c in competencies]
    kept, dropped = [], []
    for skill in skills:
        skill_tokens = tokens(skill)
        if skill_tokens and any(skill_tokens <= ct for ct in comp_tokens):
            dropped.append(skill)
        else:
            kept.append(skill)
    return kept, dropped


def wrap_terms(terms, width=CHARS_PER_LINE, sep=" | "):
    """Pack pipe-separated terms into rows no wider than `width` characters."""
    rows, current = [], ""
    for term in terms:
        candidate = f"{current}{sep}{term}" if current else term
        if current and len(candidate) > width:
            rows.append(current)
            current = term
        else:
            current = candidate
    if current:
        rows.append(current)
    return rows
