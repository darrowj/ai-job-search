# AI Job Search System
### Built by Jason Darrow | [jasondarrow.com](https://jasondarrow.com)

An AI-powered job search assistant that finds relevant job postings, enriches them with company intelligence, customizes my resume and cover letter for each role using the Claude API, and tracks my application progress from submission to offer.

Built as a hands-on learning project to develop real AI engineering skills while solving a real personal problem — finding a job.

---

## What it does

- **Scrapes job boards** across multiple titles and locations via the JSearch API (OpenWeb Ninja) — captures the full job description for each posting and outputs to `output/job_listings.xlsx` (with dated archive snapshots)
- **Enriches listings** with company intelligence — industry, size, stability, growth trend, and recent news via web search (DuckDuckGo) and NewsAPI — plus an AI **resume match score** (0–100) and match notes comparing each posting against `master_resume.json`
- **Generates an HTML report** of shortlisted jobs with company briefs, match score badges, and one-click resume tailor commands
- **Tailors resumes** using the Claude API — paste the full job description, Claude selects the best matching bullets from a 57-bullet master resume database, rewrites the summary to match
- **Generates cover letters** using the Claude API — produces a voice-matched cover letter grounded in the same bullets selected for the tailored resume, outputs a submission-ready .docx
- **Generates Word documents** — reconstructs my resume format with AI-selected bullets, outputs a submission-ready .docx file
- **Portfolio site** live at [jasondarrow.com](https://jasondarrow.com) documenting the project and journey

---

## The workflow

There are two ways to run the pipeline: the **dashboard** (recommended) or the
**command line**. Both call the same scripts and produce the same files.

### Recommended: the dashboard

```
1. Edit search_config.json
   → set titles, locations, filters, salary floor (salary set privately in .env)

2. streamlit run dashboard.py
   → opens the control panel in your browser

3. Work top to bottom through the tabs:
   Tab 1 Scrape        → run the scraper, watch the live log
   Tab 2 Review        → mark roles "Interested" right in an editable table
   Tab 3 Enrich        → pull company intel + resume match scores, read briefs, generate the HTML report
   Tab 4 Tailor        → pick a role, auto-fill the JD, tailor the resume, generate the .docx (cover letter shortcut here too)
   Tab 5 Status        → per-company enrichment / tailored / resume / cover letter / match score
   Tab 6 Cover Letter  → generate a cover letter standalone for any role (with or without a tailored resume)

4. Review, edit, export to PDF, submit
```

The dashboard is the human-in-the-loop front door — every button still runs the
scripts below, with their output streamed live into the page. See the
[Dashboard](#dashboard) section for tab details.

### Alternative: the command line

```
1. Edit search_config.json
   → set titles, locations, filters, salary floor (salary set privately in .env)

2. python3 job_scraper.py
   → output/job_listings.xlsx (canonical, filtered, deduped)
   → output/archive/job_listings_YYYY-MM-DD.xlsx (dated snapshot)

3. Open Excel → mark interesting roles as "Interested"

4. python3 enrich_jobs.py
   → pulls company intel + resume match scores for Interested rows

5. python3 report_generator.py
   → output/job_report_YYYY-MM-DD.html

6. Open HTML report in browser
   → read company briefs and match scores
   → copy tailor command for roles you want to apply to

7. python3 resume_tailor.py --company "Fidelity" \
                             --title "Technical Project Delivery Manager" \
                             --description "<paste full JD>"
   → output/tailored_Fidelity.json (match score, selected bullets)

8. python3 resume_generator.py --input output/tailored_Fidelity.json
   → personal/Jason_Darrow_Resume_Fidelity.docx

9. python3 cover_letter_generator.py --company "Fidelity" \
                                       --title "Technical Project Delivery Manager" \
                                       --description "<paste full JD>"
   → personal/CoverLetter_Fidelity.docx
   (auto-detects tailored JSON if it exists)

10. Review, edit, export to PDF, submit
```

---

## Tech stack

| Tool | Purpose |
|------|---------|
| Python 3 | Core language |
| Claude API (Anthropic) | Resume tailoring, cover letters, enrichment match scoring |
| JSearch API (OpenWeb Ninja) | Job listing search + full job descriptions |
| NewsAPI | Recent company news headlines |
| ddgs (DuckDuckGo) | Company background web search |
| python-docx | Word document generation |
| pandas + openpyxl | Excel output and enrichment |
| Streamlit | Dashboard control panel |
| requests | API calls and HTTP fetching |
| python-dotenv | Secure API key management |
| GitHub | Version control and portfolio |
| AWS S3 + Route 53 | Portfolio site hosting |

---

## Project files

```
dashboard.py                Streamlit control panel — run the whole pipeline from the browser
job_scraper.py              Search job boards, output to Excel
search_config.json          Search preferences — titles, locations, filters (committed)
enrich_jobs.py              Enrich Interested listings with company intel + resume match scores
report_generator.py         Generate HTML report from enriched listings
resume_tailor.py            AI resume tailoring via Claude API
resume_generator.py         Generate Word doc from tailored JSON
cover_letter_generator.py   AI cover letter generation via Claude API — voice-matched, grounded in tailored bullets
master_resume.json          57-bullet career database with tags and strength scores
index.html                  Portfolio site source
.env                        API keys + MIN_SALARY (never committed)
```

---

## Key design decisions

**Master resume as a database** — instead of one static resume, all career experience lives in a JSON file with 57 bullets tagged by skill category and scored by strength. The AI selects the best 5-6 per role rather than showing everything.

**Resume match scoring at enrichment** — during `enrich_jobs.py`, Claude compares `master_resume.json` against each job's full description and stores a 0–100 match score plus brief notes in the Excel. The HTML report and dashboard status tab surface the score so you can prioritize before tailoring.

**Full job descriptions captured at scrape time** — the JSearch scraper stores each posting's full text in the Excel, so resume tailoring and cover letter generation pull the description straight from the spreadsheet with no manual paste for most roles.

**Config-driven search** — search preferences (titles, locations, filters) live in `search_config.json`, committed to GitHub and documented with inline `_comment` fields. Salary floor stays private in `.env` to protect negotiating position.

**Allowlist filtering over blocklist** — rather than maintaining an ever-growing list of titles to exclude, the scraper uses a `require_title_keywords` allowlist. Any result whose title doesn't match is dropped. Eliminates noise without whack-a-mole maintenance.

**Iterative waves** — built in waves so each phase produced something useful before moving to the next. The core pipeline is complete; future changes are driven by real usage.

**Secrets management** — API keys and salary floor in `.env`, never committed to GitHub.

**Human in the loop** — Claude selects and adjusts bullets but never invents experience. Every generated resume is reviewed and edited before submission.

---

## Dashboard

A Streamlit app (`dashboard.py`) wraps the pipeline so each stage runs from a button instead of a terminal. It is the human-in-the-loop control panel — every action still calls the same scripts under the hood, with stdout streamed live into the page so you can watch the work happen.

**Launch:**

```bash
streamlit run dashboard.py
```

**Tabs:**

| Tab | What it does |
|-----|---------------|
| 1. Scrape | Runs `job_scraper.py` (writes canonical `output/job_listings.xlsx` + archive snapshot) |
| 2. Review | Edits the `Status` column in-place (`Interested` / `Skip`), saves back to Excel |
| 3. Enrich | Counts Interested jobs, runs `enrich_jobs.py` (company intel + resume match scores), renders company briefs, generates the HTML report (download or **Open in Browser**) |
| 4. Tailor | Picks one Interested role, auto-fills the job description from the scraped Excel (editable fallback), runs `resume_tailor.py`, shows match score and bullets, generates resume `.docx`; optional cover letter shortcut when a tailored JSON exists |
| 5. Status | Read-only tracker: enrichment, tailored JSON, resume DOCX, cover letter, and match score per Interested role |
| 6. Cover Letter | Standalone cover letter generation for any role — prefill from Interested jobs or enter company/title/description manually; reuses tailored JSON when available |

A status panel at the top shows total jobs, # Interested, # enriched, # tailored resumes, and the canonical file's last-modified time.

**CLI vs dashboard:** `python3 job_scraper.py` and the dashboard **Run Scraper** button both write the same canonical file. Dated history lives under `output/archive/` only.

---

## Setup

```bash
# Clone the repo
git clone https://github.com/darrowj/ai-job-search.git
cd ai-job-search

# Install dependencies
pip3 install -r requirements.txt

# Add your API keys and salary floor to .env
ANTHROPIC_API_KEY=your_key
JSEARCH_API_KEY=your_key
NEWS_API_KEY=your_key
MIN_SALARY=200000

# Edit search_config.json to set your titles, locations, and filters
# (documented inline — see _comment fields in the file)

# Run the scraper (or launch the dashboard)
python3 job_scraper.py
# streamlit run dashboard.py
```

---

## About

Built by **Jason W. Darrow** — IT Delivery Manager, US Air Force Veteran, BJJ Black Belt, and currently very much learning AI by doing.

- 🌐 [jasondarrow.com](https://jasondarrow.com)
- 💼 [linkedin.com/in/jason-w-darrow](https://linkedin.com/in/jason-w-darrow)
- 🐙 [github.com/darrowj](https://github.com/darrowj)