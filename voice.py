"""
voice.py

Single source of truth for Jason's writing voice across the pipeline.

Two things live here:

1. VOICE_RULES  — the prompt text injected into every Claude call that produces
   words Jason will put his name on.  Loaded at runtime from context/Voice.md
   so the rules are edited in one human-readable place, not duplicated in
   three Python files.  context/Voice.md is gitignored, so FALLBACK_RULES below
   carries the non-negotiable subset for anyone cloning the repo.

2. sanitize() / audit()  — deterministic post-processing.  The prompt is a
   request, not a constraint.  resume_tailor.py already learned this the hard
   way when a prompt asking for "exactly 5 Voya bullets" returned 8.  Voice is
   the same problem: Claude's house style leans on em dashes, and asking it
   nicely does not reliably stop that.  sanitize() fixes the unambiguous cases
   in code.  audit() reports the ones that need a human eye.
"""

import re

VOICE_FILE = "context/Voice.md"

# The subset that must survive even without context/Voice.md present.
FALLBACK_RULES = """
JASON'S WRITING VOICE — apply every rule without exception:

1. Double space after periods.  Two spaces, not one.  Always.
2. NO em dashes (—) and no en dashes (–).  Never.  Not as a pause, not as a
   separator, not to introduce a clause.  Use a comma, parentheses, or break
   the sentence in two.  Hyphens inside compound words (cross-functional,
   multi-million-dollar) are fine.
3. Short sentences.  One idea per sentence.  If a sentence runs long, break it.
4. No semicolons.  Colons only to introduce a list, and sparingly.
5. BANNED words and phrases — never use these:
   progressive, leveraging, synergy, results-driven, proven track record,
   passionate about, excited to, dynamic, innovative, strategic thinker,
   seeking to utilize, spearheading, impactful, seasoned professional,
   extensive background, robust, holistic, best-in-class, cutting-edge.
6. Give the reason, not just the claim.  Specifics carry the weight.
7. Direct and confident, not boastful.  State facts.  Let outcomes speak.
"""

# Extra rules that only make sense for resume prose (bullets and summary).
RESUME_VOICE_RULES = """
RESUME-SPECIFIC VOICE RULES:

- Resume summaries use implied first person.  No "I", no "he".
- Do NOT use the pattern "<noun phrase> — <verb>ing ...".  It is the single
  most recognizable AI-writing tell and it must not appear.
  Wrong: "Coordinated delivery across 30+ teams — facilitating status meetings
         and tracking risks."
  Right: "Coordinated delivery across 30+ teams, facilitating status meetings
         and tracking risks."
  Also right (better): "Coordinated delivery across 30+ teams.  Ran weekly
         status meetings and tracked risks and dependencies."
- Vary the sentence shape between bullets.  If three bullets in a row use the
  same construction, rewrite one of them.
"""

# One tell that shows up as a factual error, not a style error.  Claude counts
# only the Voya tenure and writes "6+ years", which is both wrong and a much
# weaker claim than the truth.
FACTS_GUARDRAIL = """
FACTUAL GUARDRAILS:

- Years of experience: if a years figure is used at all, it is "10+ years" in
  IT delivery.  Never compute a smaller number from a single employer's dates.
  Never write 5+, 6+, 7+, or 8+ years.
- Never invent a metric, a dollar figure, a team size, a technology, or a
  certification that is not already in the master resume.
- Never name a tool, API, framework, or vendor unless it appears in the source
  material you were given.  Do not reach for a plausible-sounding one.

NO JARGON JASON WOULD NOT SAY OUT LOUD:

- Never use a consulting or framework acronym as if it were an English word.
  Banned outright: RAID, RACI, OKR, KPI-driven, SIPOC, VOC, DMAIC, SAFe,
  "the RAID discipline", "RACI clarity", "swim lanes", "north star".
  Jason tracks risks, issues, and dependencies.  Say that in plain words.
- If a term would need explaining to a hiring manager outside IT, do not use
  it.  Write what it means instead.
"""


def _load_voice_file(path=VOICE_FILE):
    try:
        with open(path) as f:
            text = f.read().strip()
        return text or None
    except (FileNotFoundError, IsADirectoryError):
        return None


def voice_rules(resume_mode=False):
    """Return the voice rules block for a prompt.

    Prefers context/Voice.md.  Falls back to FALLBACK_RULES so the pipeline
    still enforces the essentials on a fresh clone.
    """
    base = _load_voice_file()
    if base:
        block = (
            "JASON'S WRITING VOICE — this is his own style guide.  Apply every\n"
            "rule without exception.\n\n"
            + base
        )
    else:
        block = FALLBACK_RULES

    parts = [block, FACTS_GUARDRAIL]
    if resume_mode:
        parts.append(RESUME_VOICE_RULES)
    return "\n\n".join(p.strip() for p in parts)


# ── Deterministic cleanup ──────────────────────────────────────────────────

DASHES = "—–"          # em dash, en dash
DASH_RE = re.compile(r"\s*[" + DASHES + r"]\s*")

BANNED = [
    "progressive", "leveraging", "leverage", "synergy", "results-driven",
    "proven track record", "passionate about", "excited to", "dynamic",
    "innovative", "strategic thinker", "seeking to utilize", "spearhead",
    "spearheading", "impactful", "seasoned professional", "extensive background",
    "best-in-class", "cutting-edge", "robust", "holistic", "world-class",
]

# Framework acronyms that read as consultant-speak in prose.  Matched as whole
# words so "raid" inside another word never trips it.
JARGON = [
    "RAID", "RACI", "SIPOC", "DMAIC", "SAFe", "OKR", "OKRs",
    "swim lane", "swim lanes", "north star", "KPI-driven",
]
JARGON_RE = re.compile(
    r"\b(" + "|".join(re.escape(j) for j in JARGON) + r")\b"
)

# "<something> — <lowercase -ing word>" is the construction to kill.
PARTICIPLE_TELL = re.compile(
    r"[" + DASHES + r"]\s+(" + r"|".join([
        "driving", "managing", "including", "facilitating", "advancing",
        "maintaining", "providing", "ensuring", "enabling", "delivering",
        "supporting", "coordinating", "leading", "creating", "helping",
        "allowing", "reducing", "improving", "streamlining", "positioning",
    ]) + r")\b",
    re.IGNORECASE,
)


def count_dashes(text):
    return sum(text.count(d) for d in DASHES)


def sanitize(text):
    """Remove em/en dashes and fix sentence spacing.  Returns (text, changed).

    A single dash in a sentence becomes a comma, which reads correctly in
    almost every case the model produces (it is nearly always an appositive or
    a trailing participle clause).  Strings with two or more dashes are left
    alone on purpose: a paired-dash aside turned into commas produces a run-on,
    and picking the right rewrite is a judgment call.  audit() flags those.
    """
    if not isinstance(text, str) or not text:
        return text, False

    original = text
    n = count_dashes(text)

    if n == 1:
        # Trailing dash clause or appositive.  A comma is the right swap.
        text = DASH_RE.sub(", ", text)
        # Do not stack punctuation.
        text = re.sub(r",\s*,", ", ", text)
        text = re.sub(r"([,;:])\s*,", r"\1 ", text)

    # Double space after a sentence-ending period.  The lowercase/digit/quote
    # lookbehind keeps this off initialisms like "U.S. Air Force".
    text = re.sub(r'(?<=[a-z0-9\)\]"\'])([.!?]) (?=[A-Z])', r"\1  ", text)

    # Never leave three or more spaces behind.
    text = re.sub(r"[ ]{3,}", "  ", text)

    return text, text != original


def audit(text, label=""):
    """Return a list of human-readable voice problems.  Does not modify text."""
    problems = []
    if not isinstance(text, str) or not text:
        return problems

    n = count_dashes(text)
    if n >= 2:
        problems.append(
            f"{label}: {n} dashes in one string, left unchanged (a paired-dash "
            f"aside needs a real rewrite, not a comma swap)."
        )
    elif n == 1:
        problems.append(f"{label}: dash found and replaced with a comma, verify it reads right.")

    if PARTICIPLE_TELL.search(text):
        problems.append(
            f"{label}: uses the '<phrase> — <verb>ing' construction.  This is "
            f"the loudest AI tell on the page.  Rewrite the sentence."
        )

    if ";" in text:
        problems.append(f"{label}: contains a semicolon.  Jason does not use them.")

    jargon_hits = sorted(set(JARGON_RE.findall(text)))
    if jargon_hits:
        problems.append(
            f"{label}: consultant jargon present: {', '.join(jargon_hits)}.  "
            f"Jason does not use these words.  Say what it means in plain English."
        )

    lowered = text.lower()
    hits = sorted({w for w in BANNED if w in lowered})
    if hits:
        problems.append(f"{label}: banned words present: {', '.join(hits)}.")

    if re.search(r"\bMay\b.{0,40}\b(laid off|layoff|eliminated|role ended)\b", text, re.I) \
       or re.search(r"\b(laid off|layoff|eliminated|role ended)\b.{0,40}\bMay\b", text, re.I):
        problems.append(
            f"{label}: says the role ended in May.  It ended in JUNE 2026 "
            f"(notified in May, last day 6/15/2026)."
        )

    m = re.search(r"\b([1-9])\+?\s*years\b", lowered)
    if m and int(m.group(1)) < 10:
        problems.append(
            f"{label}: states '{m.group(0)}'.  Jason's framing is 10+ years.  "
            f"Claude counts one employer's dates and undersells the record."
        )

    return problems
