import anthropic
import json
import os
import argparse
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

import voice
import band

# Load API keys from .env
load_dotenv()

# Load your master resume
with open("master_resume.json", "r") as f:
    master_resume = json.load(f)


# ── Drop superseded bullets ────────────────────────────────────────────────
# A bullet can declare "supersedes": ["b017"] to mark an older bullet as
# replaced.  The old bullet stays in master_resume.json as history, but it must
# never reach Claude, or the weaker wording can be selected instead of the
# rewrite.  Same principle as the bullet-count trim below: the intent is
# unambiguous, so enforce it in code rather than asking the prompt nicely.

def active_resume(resume):
    """Return a copy of the resume with superseded bullets removed."""
    retired = {
        old_id
        for exp in resume.get("experience", [])
        for b in exp.get("bullets", [])
        for old_id in b.get("supersedes", [])
    }
    if not retired:
        return resume

    trimmed = dict(resume)
    trimmed["experience"] = [
        {**exp, "bullets": [
            b for b in exp.get("bullets", []) if b.get("id") not in retired
        ]}
        for exp in resume.get("experience", [])
    ]
    print(f"Excluded {len(retired)} superseded bullet(s): "
          f"{', '.join(sorted(retired))}", flush=True)
    return trimmed

# ── Fetch job description from URL ─────────────────────────────────────────

MIN_DESCRIPTION_CHARS = 200  # anything shorter means JS-rendered page returned a shell

def fetch_job_description(url):
    print(f"Fetching job description from: {url}", flush=True)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)

        # Non-200 means access denied, redirect wall, or other block
        if response.status_code != 200:
            print(f"⚠ HTTP {response.status_code} returned — fetch blocked.", flush=True)
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove noise
        for tag in soup(["nav", "header", "footer", "script", "style", "aside"]):
            tag.decompose()

        # Get clean text
        text = soup.get_text(separator=" ", strip=True)

        # Trim to reasonable size for the API
        text = text[:4000]

        if len(text) >= MIN_DESCRIPTION_CHARS:
            print(f"Fetched {len(text)} characters of job description.", flush=True)
            return text

        # JS-rendered page — only a shell came back
        print(f"⚠ Only {len(text)} characters returned — page is likely JS-rendered.", flush=True)
        return None

    except Exception as e:
        print(f"Error fetching URL: {e}", flush=True)
        return None


def prompt_for_manual_description():
    """Ask the user to paste the job description directly into the terminal."""
    print()
    print("─" * 60)
    print("The job posting couldn't be fetched automatically.")
    print("Please paste the job description below.")
    print("When done, press Enter then type END on its own line.")
    print("─" * 60)
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip().upper() == "END":
            break
        lines.append(line)
    text = "\n".join(lines).strip()
    print(f"Received {len(text)} characters of job description.", flush=True)
    return text or None

# ── Pass 1: read the requirements before looking at the resume ────────────
# A career coach reviewing the Intact IT Development Manager resume went
# straight to the posting's "expertise you bring" list and found two of four
# requirements unaddressed -- including an entire technical line (cloud, SOA,
# DevOps, GitHub, containerization) that appeared nowhere on the page.  The
# pipeline had returned match_score 82.
#
# The reason it missed is structural: a single API call was asked to pick the
# bullets AND grade the fit.  A model that already knows which bullets exist
# will quietly decide the requirements it can satisfy are the important ones.
# So requirement extraction is its own call and is never shown the resume.
# It cannot rationalize what it cannot see.  Same principle as pulling the
# priority decision out of a prompt and into a readable ladder: separate the
# judgment from the thing being judged.

def extract_requirements(job_title, job_description):
    """Return the posting's stated requirements, extracted blind to the resume."""
    print("Reading job requirements...", flush=True)

    client = anthropic.Anthropic()

    prompt = f"""
Read this job posting and extract what it actually requires of a candidate.

Focus on the qualifications / requirements / "what you bring" section.  That is
the section a recruiter and an ATS screen against.  Also include any hard
requirement stated elsewhere in the posting.

For each requirement:
- "text": the requirement, quoted or closely paraphrased from the posting
- "must_have": true if stated as required, minimum, or "requires"; false if
  stated as preferred, desired, a plus, or nice to have
- "category": one of education, experience, management, technical, domain, certification
- "terms": the specific words an ATS would match on, taken VERBATIM from the
  posting, PLUS obvious equivalents a resume might legitimately use (for
  "supervisory" also include "supervised", "manager", "team lead").  Every
  term in this list must be a synonym for the SAME thing, because matching any
  one of them counts the requirement as met.  Do not invent terms the posting
  does not imply.

CRITICAL — split compound requirements into separate entries.  A requirement
that names several distinct technologies is several requirements.  So
"An understanding of IT applications and technologies, including cloud
architecture, Service-oriented Architecture, DevOps, GitHub and
containerization" becomes FIVE entries, one each for cloud architecture, SOA,
DevOps, GitHub and containerization.  Never put two different technologies in
one entry's terms list.  A candidate strong in one and absent in the other four
must not score as covered, which is exactly what happens if you group them.

Do not judge any candidate.  You are only reading the posting.

JOB TITLE: {job_title}

JOB POSTING:
{job_description}

Return only JSON in this exact format:
{{
  "posting_title": "the exact job title as written in the posting",
  "requirements": [
    {{
      "id": "r1",
      "text": "...",
      "must_have": true,
      "category": "technical",
      "terms": ["term one", "term two"]
    }}
  ]
}}
"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text
    parsed = json.loads(text[text.find("{"):text.rfind("}") + 1])

    reqs = parsed.get("requirements", [])
    musts = sum(1 for r in reqs if r.get("must_have"))
    print(f"Found {len(reqs)} requirement(s), {musts} stated as required.", flush=True)
    return parsed


# ── Tailor resume using Claude API ────────────────────────────────────────

def _requirements_block(requirements):
    """Render extracted requirements for the selection prompt."""
    reqs = (requirements or {}).get("requirements", [])
    if not reqs:
        return ""
    lines = ["REQUIREMENTS EXTRACTED FROM THIS POSTING (address these first):"]
    for r in reqs:
        flag = "REQUIRED" if r.get("must_have") else "preferred"
        terms = ", ".join(r.get("terms", []))
        lines.append(f"  [{flag}] ({r.get('category','')}) {r.get('text','')}")
        if terms:
            lines.append(f"      ATS terms: {terms}")
    lines.append("")
    lines.append(
        "Select bullets that give concrete evidence for as many of these as the\n"
        "master resume honestly supports.  Where the master resume contains a\n"
        "term the posting asks for, prefer the bullet that contains it.  Never\n"
        "claim experience the master resume does not contain -- an uncovered\n"
        "requirement is reported as a gap, which is the correct outcome."
    )
    return "\n".join(lines)


def _skill_pool(resume):
    """Flatten master skills into one list.  The tailor may only select from this."""
    pool = []
    for group in (resume.get("skills") or {}).values():
        if isinstance(group, list):
            pool.extend(group)
    return sorted(set(pool))


def tailor_resume(job_title, job_description, requirements=None):
    print(f"Tailoring resume for: {job_title}...", flush=True)

    client = anthropic.Anthropic()

    prompt = f"""
You are helping Jason Darrow tailor his own resume.  Everything you write goes
out under his name, so it has to sound like him, not like a resume template and
not like an AI.  I will give you his master resume in JSON format and a job
description.  Your job is to:

1. Read the job description carefully and identify the top 5-6 required
   skills and experiences
2. Select the most relevant bullets from the master resume that match.
   - Voya Financial (most recent role): select exactly 5 bullets
   - Bank of America roles: select 2-3 bullets total across all BoA titles
   - Do not include bullets from older roles (Click2Learn, etc.)
3. SELECT, do not rewrite.  Return each bullet's text from the master resume
   VERBATIM unless the job description gives you a concrete reason to change a
   word.  The master bullets were written by a professional resume writer and
   already sound like Jason.  If you must edit, change the smallest number of
   words that does the job (swap a term for the JD's term, drop a clause that
   is irrelevant to this role).  Do not restructure a sentence you are only
   lightly editing.  Rewriting every bullet is the failure mode here.
4. Write the tailored summary from the closest-matching summary profile in the
   master resume, adjusted for this role.  Same rule: edit, do not replace.
   If the posting states a hard requirement the master resume genuinely
   satisfies (years of experience, a degree, supervisory experience, a
   certification), make sure the summary says so plainly.
5. Select 9 to 12 entries from COMPETENCY POOL below for the Core Competencies
   band, ordered by relevance to this posting.  Copy them EXACTLY as written.
   Do not invent a competency that is not in the pool.
6. Select 6 to 10 terms from SKILL POOL below that this posting actually asks
   about, most relevant first.  Copy them EXACTLY.  Do not add a skill that is
   not in the pool, however well it would match -- a skill Jason cannot defend
   in an interview is worse than a missing keyword.  Two more rules:
   - Do NOT repeat anything you already put in tailored_competencies, or say
     the same thing in different words.  If the band says "Agile & Waterfall
     Delivery", do not also list Agile and Waterfall.  This row exists to add
     the concrete terms the competencies cannot carry (tools, languages,
     platforms, domains), not to restate them.
   - Do not dump the whole pool.  Terms the posting never asks about dilute the
     ones it does.
7. Pick the headline.  "tailored_headline" is the role label under Jason's
   name and must come from HEADLINE TITLE POOL below, verbatim.  Choose the
   one that matches how THIS employer describes the job.  A software vendor
   hiring someone to deliver to its own customers should not be reading
   "IT Leader", which positions him as internal IT.
8. Pick 3 terms from COMPETENCY POOL for "tailored_tagline", the line directly
   under the headline.  At most ONE of them may also appear in
   tailored_competencies.  The tagline is read in the first two seconds and
   the band is read second, so repeating the single core term is emphasis but
   repeating all three wastes the best space on the page.  Pick terms that say
   something the band does not.
9. Return the JSON described at the bottom.

LENGTH BUDGET (this resume must fit on two pages):
- tailored_summary: 650 characters maximum
- each bullet: 230 characters maximum

{_requirements_block(requirements)}

{voice.voice_rules(resume_mode=True)}

HEADLINE TITLE POOL (select exactly 1, verbatim):
{json.dumps((master_resume.get("headline") or {}).get("title_pool", []), indent=2)}

COMPETENCY POOL (select 9-12, verbatim):
{json.dumps(master_resume.get("competency_pool") or master_resume.get("core_competencies", []), indent=2)}

SKILL POOL (select only what this posting asks about, verbatim):
{json.dumps(_skill_pool(master_resume), indent=2)}

MASTER RESUME:
{json.dumps(active_resume(master_resume), indent=2)}

JOB TITLE: {job_title}

JOB DESCRIPTION:
{job_description}

Return your response in this exact JSON format:
{{
  "tailored_summary": "the best fitting summary reworded for this role",
  "selected_bullets": [
    {{
      "company": "company name",
      "title": "job title",
      "bullet": "the tailored bullet text"
    }}
  ],
  "tailored_headline": "one entry from HEADLINE TITLE POOL",
  "tailored_tagline": ["term 1", "term 2", "term 3"],
  "tailored_competencies": ["competency 1", "competency 2"],
  "technical_skills": ["skill 1", "skill 2"],
  "key_skills": ["skill1", "skill2", "skill3"],
  "match_score": 85
}}
"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    response_text = message.content[0].text

    # Parse the JSON response
    start = response_text.find("{")
    end = response_text.rfind("}") + 1
    json_str = response_text[start:end]
    result = json.loads(json_str)

    return validate_selection(result)


# ── Post-parse validation ─────────────────────────────────────────────────
# The prompt above asks for exactly 5 Voya bullets and 2-3 from Bank of
# America, but a prompt is a request, not a constraint — the model overshoots.
# One observed run returned 8 Voya bullets, which resume_generator.py dutifully
# wrote into the document and pushed the resume to three pages with nothing
# flagging it.  These checks make that visible and correct the one case that
# reliably breaks the layout.

MAX_VOYA_BULLETS   = 5
BOA_BULLET_RANGE   = (2, 3)
# Both length ceilings are set just above the longest values seen in a
# confirmed 2-page resume (tailored_MIT_AICR.json: 625-char summary, longest
# bullet 227 chars).  Set them any tighter and the check fires on known-good
# output, which is the fastest way to train yourself to ignore warnings.
MAX_SUMMARY_CHARS  = 650
MAX_BULLET_CHARS   = 230


def _normalize(text):
    """Whitespace- and dash-insensitive form, for verbatim comparison."""
    text = (text or "").replace("—", ",").replace("–", ",")
    return " ".join(text.replace(",", " ").split()).lower()


def _master_bullet_texts():
    return {
        _normalize(b.get("text", ""))
        for exp in master_resume.get("experience", [])
        for b in exp.get("bullets", [])
    }


def validate_selection(result):
    """Warn on anything that will blow the two-page layout; trim Voya to 5.

    Only the Voya overshoot is corrected automatically — it is the one that
    directly drives page count, and the intended number is unambiguous.
    Everything else is reported so you can judge it in review.
    """
    bullets = result.get("selected_bullets", []) or []

    def is_voya(b):
        return "voya" in str(b.get("company", "")).lower()

    def is_boa(b):
        return "bank of america" in str(b.get("company", "")).lower()

    voya  = [b for b in bullets if is_voya(b)]
    boa   = [b for b in bullets if is_boa(b)]
    other = [b for b in bullets if not is_voya(b) and not is_boa(b)]

    warnings = []

    # 1. Voya count — the one we fix, because the target is unambiguous.
    if len(voya) > MAX_VOYA_BULLETS:
        dropped = voya[MAX_VOYA_BULLETS:]
        voya = voya[:MAX_VOYA_BULLETS]
        warnings.append(
            f"Claude returned {len(dropped) + MAX_VOYA_BULLETS} Voya bullets; "
            f"trimmed to {MAX_VOYA_BULLETS}. Dropped:"
        )
        for b in dropped:
            warnings.append(f"    - {b.get('bullet', '')[:90]}...")
        result["selected_bullets"] = voya + boa + other
    elif len(voya) < MAX_VOYA_BULLETS:
        warnings.append(
            f"Only {len(voya)} Voya bullet(s) returned (expected {MAX_VOYA_BULLETS})."
        )

    # 2. BoA count — reported, not corrected. Which two to keep is a judgment call.
    lo, hi = BOA_BULLET_RANGE
    if boa and not (lo <= len(boa) <= hi):
        warnings.append(
            f"{len(boa)} Bank of America bullets returned (expected {lo}-{hi})."
        )

    # 3. Length budget — the other driver of a three-page resume.
    summary_len = len(result.get("tailored_summary", "") or "")
    if summary_len > MAX_SUMMARY_CHARS:
        warnings.append(
            f"Summary is {summary_len} chars (target ≤ {MAX_SUMMARY_CHARS}) — "
            f"about {(summary_len - MAX_SUMMARY_CHARS) // 105 + 1} extra line(s)."
        )

    long_bullets = [
        b for b in result.get("selected_bullets", [])
        if len(b.get("bullet", "")) > MAX_BULLET_CHARS
    ]
    if long_bullets:
        warnings.append(
            f"{len(long_bullets)} bullet(s) over {MAX_BULLET_CHARS} chars:"
        )
        for b in long_bullets:
            warnings.append(
                f"    - {len(b.get('bullet', ''))} chars: {b.get('bullet', '')[:70]}..."
            )

    # 4. Voice — em dashes, AI tells, banned words, undersold years.
    # Run AFTER the length checks so the char counts above reflect what Claude
    # actually returned.  sanitize() only ever shortens or leaves alone.
    voice_notes = []

    summary = result.get("tailored_summary", "") or ""
    cleaned, changed = voice.sanitize(summary)
    if changed:
        result["tailored_summary"] = cleaned
    voice_notes += voice.audit(cleaned, "Summary")

    verbatim = _master_bullet_texts()
    rewritten = 0
    for i, b in enumerate(result.get("selected_bullets", []), start=1):
        text = b.get("bullet", "") or ""
        cleaned, changed = voice.sanitize(text)
        if changed:
            b["bullet"] = cleaned
        voice_notes += voice.audit(cleaned, f"Bullet {i}")
        if _normalize(cleaned) not in verbatim:
            rewritten += 1

    if voice_notes:
        warnings.append("Voice check:")
        warnings += [f"    - {n}" for n in voice_notes]

    # How much did Claude actually rewrite?  High counts mean it ignored the
    # "select, do not rewrite" instruction and you are shipping its prose
    # instead of your resume writer's.
    total = len(result.get("selected_bullets", []))
    if total and rewritten > total // 2:
        warnings.append(
            f"{rewritten} of {total} bullets differ from the master resume text.  "
            f"Claude rewrote more than it selected — reread them before sending."
        )

    # 5. Pool membership.  The competency band and the skills line are the
    # densest ATS real estate on the page, which makes them the most tempting
    # place for the model to helpfully add a keyword the posting wants and
    # Jason does not have.  The pools are the honesty boundary, so anything
    # outside them is dropped in code rather than argued with in the prompt.
    pool = master_resume.get("competency_pool") or master_resume.get("core_competencies", [])
    kept, dropped = _filter_to_pool(result.get("tailored_competencies", []), pool)
    result["tailored_competencies"] = kept or list(pool[:10])
    if dropped:
        warnings.append(
            f"Dropped {len(dropped)} competenc(ies) not in the pool: {', '.join(dropped)}"
        )
    if kept and not (9 <= len(kept) <= 12):
        warnings.append(f"{len(kept)} competencies selected (expected 9-12).")

    # The headline and its tagline sit above everything else on the page and
    # were static until 8/4.  Same honesty boundary as the band: the role label
    # comes from title_pool, the tagline terms from competency_pool.
    head_cfg = master_resume.get("headline") or {}
    title_pool = head_cfg.get("title_pool") or []
    if title_pool:
        chosen, rejected = _filter_to_pool([result.get("tailored_headline")], title_pool)
        result["tailored_headline"] = chosen[0] if chosen else head_cfg.get("title")
        if rejected:
            warnings.append(
                f"Headline '{rejected[0]}' is not in the title pool — fell back to "
                f"'{result['tailored_headline']}'."
            )

    tagline, rejected = _filter_to_pool(result.get("tailored_tagline", []), pool)
    if rejected:
        warnings.append(f"Dropped {len(rejected)} tagline term(s) not in the pool: "
                        f"{', '.join(rejected)}")
    if tagline:
        result["tailored_tagline"] = tagline[:3]
        echoed = band.dedupe_skills(result["tailored_tagline"],
                                    result["tailored_competencies"])[1]
        if len(echoed) > 1:
            warnings.append(
                f"{len(echoed)} of {len(result['tailored_tagline'])} tagline terms "
                f"repeat the competency band ({', '.join(echoed)}).  One repeat is "
                f"emphasis, more is wasted space at the top of the page."
            )

    skills_pool = _skill_pool(master_resume)
    kept, dropped = _filter_to_pool(result.get("technical_skills", []), skills_pool)
    if dropped:
        warnings.append(
            f"Dropped {len(dropped)} skill(s) Jason cannot claim: {', '.join(dropped)}"
        )

    # The skills row sits directly under the competency band, so anything it
    # repeats is visible duplication in the densest keyword block on the page.
    # Prompted-only enforcement did not hold: the Attensi run returned all 22
    # pool terms, ten of which restated a competency printed two lines above.
    kept, duped = band.dedupe_skills(kept, result.get("tailored_competencies", []))
    if duped:
        warnings.append(
            f"Dropped {len(duped)} skill(s) already in the competency band: "
            f"{', '.join(duped)}"
        )
    result["technical_skills"] = kept
    if len(kept) > band.MAX_SKILL_TERMS:
        warnings.append(
            f"{len(kept)} skill terms selected (expected {band.MAX_SKILL_TERMS} or "
            f"fewer).  Trim the ones this posting never asks about."
        )

    if warnings:
        print("", flush=True)
        print("─" * 68, flush=True)
        print("Selection review:", flush=True)
        for w in warnings:
            print(f"  ⚠ {w}" if not w.startswith("    ") else w, flush=True)
        print("─" * 68, flush=True)

    return result

# ── Pass 2: coverage gate ─────────────────────────────────────────────────
# Checked in Python, not asked for in a prompt.  Prompt-only enforcement has now
# failed three times in this repo (bullet counts, em dashes, and this).  Anything
# that must be true of the output gets checked in code.
#
# The three-way verdict is the point.  MISSING and WEAK look identical on a
# finished resume and need opposite responses:
#
#   COVERED — evidence is on the page the employer will read.
#   WEAK    — evidence exists in master_resume.json and did not get selected.
#             A pipeline bug, fixable in thirty seconds by hand.
#   MISSING — no evidence anywhere.  Not a bug.  Either add a real bullet to
#             the master file, address it in the cover letter, or apply knowing
#             the gap is there.  The tool must never quietly close this one.


def _resume_facing_text(result, resume):
    """Everything an ATS will actually read on the generated document."""
    parts = [result.get("tailored_summary", "")]
    parts += [b.get("bullet", "") for b in result.get("selected_bullets", [])]
    parts += result.get("tailored_competencies", []) or []
    parts += result.get("technical_skills", []) or []
    # Static sections the template always prints.
    for e in resume.get("education", []):
        parts += [e.get("degree", ""), e.get("school", "")]
    # Only ACTIVE certifications.  An expired credential is real evidence, but
    # it is not on the page, so it belongs in the master pool where it surfaces
    # as WEAK -- "you have this, go put it back on" -- rather than silently
    # scoring as covered.  The expired AWS Solutions Architect cert is exactly
    # the case that caught this: it scored the Intact cloud requirement as met
    # on a credential no reader would ever see.
    for c in resume.get("certifications", []):
        if isinstance(c, str):
            parts.append(c)
        elif c.get("status", "active") == "active":
            parts.append(c.get("name", ""))
    # Job titles are evidence.  "Technical Project Team Manager" answers a
    # supervisory requirement even when no bullet uses the word.
    for exp in resume.get("experience", []):
        parts += [exp.get("title", ""), exp.get("company", ""),
                  exp.get("description", "")]
    # Projects print as a name line plus bullets.  The master "description"
    # field is not rendered, so it must not count as coverage.
    for proj in resume.get("projects", []):
        if isinstance(proj, dict):
            parts.append(proj.get("name", ""))
            parts += [str(b) for b in proj.get("bullets", [])]
        else:
            parts.append(str(proj))
    return " \n ".join(str(p) for p in parts if p).lower()


def _master_text(resume):
    """Everything available in the master file, selected or not."""
    parts = [b.get("text", "")
             for exp in resume.get("experience", [])
             for b in exp.get("bullets", [])]
    parts += (resume.get("competency_pool") or []) + resume.get("core_competencies", [])
    parts += _skill_pool(resume)
    # summaries is a list of profile objects in v4 and was a dict earlier.
    summaries = resume.get("summaries") or []
    for s in (summaries.values() if isinstance(summaries, dict) else summaries):
        parts.append(s if isinstance(s, str) else s.get("text", ""))
    return " \n ".join(str(p) for p in parts if p).lower()


def _filter_to_pool(selected, pool):
    """Keep only entries that appear in the pool.  Returns (kept, dropped)."""
    index = {p.lower().strip(): p for p in pool}
    kept, dropped = [], []
    for item in selected or []:
        match = index.get(str(item).lower().strip())
        if match and match not in kept:
            kept.append(match)
        elif not match:
            dropped.append(str(item))
    return kept, dropped


def check_coverage(requirements, result, resume):
    """Score the tailored output against the posting's stated requirements."""
    reqs = (requirements or {}).get("requirements", [])
    if not reqs:
        return result

    on_page = _resume_facing_text(result, resume)
    in_master = _master_text(resume)

    coverage, gaps = [], []
    earned = possible = 0

    for r in reqs:
        terms = [t for t in r.get("terms", []) if t and len(str(t)) > 2]
        hit_page = [t for t in terms if str(t).lower() in on_page]
        hit_master = [t for t in terms
                      if str(t).lower() in in_master and t not in hit_page]

        if hit_page:
            verdict = "COVERED"
        elif hit_master:
            verdict = "WEAK"
        else:
            verdict = "MISSING"

        weight = 2 if r.get("must_have") else 1
        possible += weight
        earned += weight if verdict == "COVERED" else (weight * 0.5 if verdict == "WEAK" else 0)

        entry = {
            "id": r.get("id"),
            "requirement": r.get("text"),
            "must_have": bool(r.get("must_have")),
            "category": r.get("category"),
            "verdict": verdict,
            "matched_on_resume": hit_page,
            "available_in_master": hit_master,
            "unmatched_terms": [t for t in terms
                                if t not in hit_page and t not in hit_master],
        }
        coverage.append(entry)
        if verdict != "COVERED":
            gaps.append(entry)

    score = round(100 * earned / possible) if possible else 0
    result["requirements"] = reqs
    result["coverage"] = coverage
    result["coverage_score"] = score
    result["model_match_score"] = result.pop("match_score", None)

    # ── Report ────────────────────────────────────────────────────────────
    print("", flush=True)
    print("=" * 68, flush=True)
    print(f"REQUIREMENTS COVERAGE — {score}/100", flush=True)
    if result.get("model_match_score") is not None:
        print(f"(the model graded itself {result['model_match_score']}; "
              f"this number is computed from the posting)", flush=True)
    print("=" * 68, flush=True)

    mark = {"COVERED": "✓", "WEAK": "~", "MISSING": "✗"}
    for c in coverage:
        req = "REQUIRED" if c["must_have"] else "preferred"
        print(f"{mark[c['verdict']]} [{req}] {c['requirement'][:88]}", flush=True)
        if c["matched_on_resume"]:
            print(f"      matched: {', '.join(c['matched_on_resume'][:6])}", flush=True)
        if c["verdict"] == "WEAK":
            print(f"      IN YOUR MASTER FILE BUT NOT ON THE PAGE: "
                  f"{', '.join(c['available_in_master'][:6])}", flush=True)
        if c["verdict"] == "MISSING":
            print(f"      no evidence anywhere for: "
                  f"{', '.join(c['unmatched_terms'][:6])}", flush=True)

    blocking = [c for c in gaps if c["must_have"]]
    if blocking:
        print("", flush=True)
        print("-" * 68, flush=True)
        print(f"{len(blocking)} REQUIRED item(s) not covered.  This is what gets you", flush=True)
        print("screened out before a human reads anything.  Before you apply:", flush=True)
        for c in blocking:
            if c["verdict"] == "WEAK":
                print(f"  • {c['requirement'][:70]}", flush=True)
                print(f"    → you HAVE this.  Surface it: {', '.join(c['available_in_master'][:4])}", flush=True)
            else:
                print(f"  • {c['requirement'][:70]}", flush=True)
                print(f"    → no evidence.  Add a real bullet to master_resume.json,", flush=True)
                print(f"      handle it in the cover letter, or apply knowing the gap.", flush=True)
        print("-" * 68, flush=True)

    return result


# ── Main ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tailor resume to a job description")
    parser.add_argument("--title",       help="Job title (optional if using --url)")
    parser.add_argument("--company",     required=True, help="Company name")
    parser.add_argument("--description", help="Job description text")
    parser.add_argument("--url",         help="URL of the job posting page")
    args = parser.parse_args()

    # Get description from URL or direct input
    if args.url:
        description = fetch_job_description(args.url)
        if not description:
            description = prompt_for_manual_description()
        if not description:
            print("No job description provided. Exiting.")
            exit(1)
        title = args.title or "Position"
    elif args.description:
        description = args.description
        title = args.title or "Position"
    else:
        print("Error: provide either --url or --description")
        exit(1)

    # Pass 1 — read the posting blind to the resume, so the requirements are
    # whatever the employer wrote, not whatever we happen to be able to answer.
    requirements = extract_requirements(title, description)

    posting_title = (requirements or {}).get("posting_title") or ""
    if posting_title and posting_title.strip().lower() != (title or "").strip().lower():
        print(f"• Posting title is \"{posting_title}\" (you passed \"{title}\").  "
              f"Consider matching it in the header.", flush=True)

    # Pass 2 — select against those requirements.
    result = tailor_resume(title, description, requirements)

    # Pass 3 — check, in code, whether the selection actually covered them.
    result = check_coverage(requirements, result, master_resume)

    # Save output named by company into output/
    os.makedirs("output", exist_ok=True)
    output_file = os.path.join("output", f"tailored_{args.company.replace(' ', '_')}.json")
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nTailoring complete.", flush=True)
    print(f"Coverage score:   {result.get('coverage_score', 'n/a')} / 100  (computed)", flush=True)
    print(f"Model self-score: {result.get('model_match_score', 'n/a')} / 100", flush=True)
    print(f"Bullets selected: {len(result.get('selected_bullets', []))}", flush=True)
    print(f"Competencies:     {len(result.get('tailored_competencies', []))}", flush=True)
    print(f"Technical skills: {', '.join(result.get('technical_skills', [])) or 'none selected'}", flush=True)
    print(f"Saved to:         {output_file}", flush=True)