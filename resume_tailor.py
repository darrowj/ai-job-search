import anthropic
import json
import os
import argparse
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

import voice

# Load API keys from .env
load_dotenv()

# Load your master resume
with open("master_resume.json", "r") as f:
    master_resume = json.load(f)

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

# ── Tailor resume using Claude API ────────────────────────────────────────

def tailor_resume(job_title, job_description):
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
5. Return a tailored resume summary and the selected bullets in JSON format

LENGTH BUDGET (this resume must fit on two pages):
- tailored_summary: 650 characters maximum
- each bullet: 230 characters maximum

{voice.voice_rules(resume_mode=True)}

MASTER RESUME:
{json.dumps(master_resume, indent=2)}

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

    if warnings:
        print("", flush=True)
        print("─" * 68, flush=True)
        print("Selection review:", flush=True)
        for w in warnings:
            print(f"  ⚠ {w}" if not w.startswith("    ") else w, flush=True)
        print("─" * 68, flush=True)

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

    # Run the tailoring
    result = tailor_resume(title, description)

    # Save output named by company into output/
    os.makedirs("output", exist_ok=True)
    output_file = os.path.join("output", f"tailored_{args.company.replace(' ', '_')}.json")
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nTailoring complete.", flush=True)
    print(f"Match score:  {result['match_score']} / 100", flush=True)
    print(f"Key skills:   {', '.join(result['key_skills'])}", flush=True)
    print(f"Bullets selected: {len(result.get('selected_bullets', []))}", flush=True)
    print(f"Saved to:     {output_file}", flush=True)