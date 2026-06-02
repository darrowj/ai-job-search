# AI Job Search System
### Built by Jason Darrow | [jasondarrow.com](https://jasondarrow.com)

An AI-powered job search assistant that finds relevant job postings, enriches them with company intelligence, customizes my resume and cover letter for each role using the Claude API, and tracks my application progress from submission to offer.

Built as a hands-on learning project to develop real AI engineering skills while solving a real personal problem — finding a job.

---

## What it does

- **Scrapes job boards** across multiple titles and locations via the Adzuna API — outputs to `output/job_listings.xlsx` (with dated archive snapshots)
- **Enriches listings** with company intelligence — industry, size, stability, growth trend, and recent news via Wikipedia and NewsAPI
- **Generates an HTML report** of shortlisted jobs with company briefs and one-click resume tailor commands
- **Tailors resumes** using the Claude API — reads a real job posting URL, selects the best matching bullets from a 53-bullet master resume database, rewrites the summary to match
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
   Tab 1 Scrape   → run the scraper, watch the live log
   Tab 2 Review   → mark roles "Interested" right in an editable table
   Tab 3 Enrich   → pull company intel, read briefs, generate the HTML report
   Tab 4 Tailor   → pick a role, tailor the resume, generate the .docx
   Tab 5 Status   → see per-company enrichment / tailored / resume state

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
   → pulls company intel for Interested rows
   → generates the HTML report

5. Open HTML report in browser
   → read company briefs
   → copy tailor command for roles you want to apply to

6. python3 resume_tailor.py --company "Fidelity" \
                             --title "Technical Project Delivery Manager" \
                             --url "https://linkedin.com/jobs/..."
   → output/tailored_Fidelity.json (match score, selected bullets)

7. python3 resume_generator.py --input output/tailored_Fidelity.json
   → Jason_Darrow_Resume.docx

8. Review, edit, export to PDF, submit
```

---

## Tech stack

| Tool | Purpose |
|------|---------|
| Python 3 | Core language |
| Claude API (Anthropic) | Resume tailoring and bullet selection |
| Adzuna API | Job listing search across US locations |
| NewsAPI | Recent company news headlines |
| Wikipedia API | Company background data |
| python-docx | Word document generation |
| pandas + openpyxl | Excel output and enrichment |
| BeautifulSoup + requests | Job description fetching from URLs |
| python-dotenv | Secure API key management |
| GitHub | Version control and portfolio |
| AWS S3 + Route 53 | Portfolio site hosting |

---

## Project files

```
dashboard.py            Streamlit control panel — run the whole pipeline from the browser
job_scraper.py          Search job boards, output to Excel
search_config.json      Search preferences — titles, locations, filters (committed)
enrich_jobs.py          Enrich Interested listings with company intel
report_generator.py     Generate HTML report from enriched listings
resume_tailor.py        AI resume tailoring via Claude API
resume_generator.py     Generate Word doc from tailored JSON
master_resume.json      53-bullet career database with tags and strength scores
index.html              Portfolio site source
.env                    API keys + MIN_SALARY (never committed)
```

---

## Key design decisions

**Master resume as a database** — instead of one static resume, all career experience lives in a JSON file with 53 bullets tagged by skill category and scored by strength. The AI selects the best 5-6 per role rather than showing everything.

**Config-driven search** — search preferences (titles, locations, filters) live in `search_config.json`, committed to GitHub and documented with inline `_comment` fields. Salary floor stays private in `.env` to protect negotiating position.

**Allowlist filtering over blocklist** — rather than maintaining an ever-growing list of titles to exclude, the scraper uses a `require_title_keywords` allowlist. Any result whose title doesn't match is dropped. Eliminates noise without whack-a-mole maintenance.

**Iterative waves** — built in waves (0-6) so each phase produces something useful before moving to the next. No big bang releases.

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
| 3. Enrich | Counts Interested jobs, runs `enrich_jobs.py`, renders company briefs, generates the HTML report |
| 4. Tailor | Picks one Interested role, runs `resume_tailor.py` (URL or pasted JD), shows match score and bullets, generates a per-company `.docx` |
| 5. Status | Read-only tracker showing per-company enrichment / tailored / resume state from files on disk |

A status panel at the top shows total jobs, # Interested, # enriched, # tailored resumes, and the canonical file's last-modified time.

**CLI vs dashboard:** `python3 job_scraper.py` and the dashboard **Run Scraper** button both write the same canonical file. Dated history lives under `output/archive/` only.

---

## Setup

```bash
# Clone the repo
git clone https://github.com/darrowj/ai-job-search.git
cd ai-job-search

# Install dependencies
pip3 install anthropic requests beautifulsoup4 python-dotenv \
             pandas openpyxl python-docx streamlit

# Add your API keys and salary floor to .env
ANTHROPIC_API_KEY=your_key
ADZUNA_APP_ID=your_id
ADZUNA_APP_KEY=your_key
NEWS_API_KEY=your_key
MIN_SALARY=200000

# Edit search_config.json to set your titles, locations, and filters
# (documented inline — see _comment fields in the file)

# Run the scraper
python3 job_scraper.py
```

---

## Project status

| Wave | Description | Status |
|------|-------------|--------|
| 0 | Master resume JSON database | ✅ Complete |
| 1 | Job scraper — Adzuna API, config-driven filters, Excel output | ✅ Complete |
| 2 | AI resume tailoring + Word doc generation | ✅ Complete |
| 2.5 | Company intelligence enrichment | ✅ Complete |
| 3 | HTML job report | ✅ Complete |
| 4 | Portfolio site — jasondarrow.com | ✅ Complete |
| 5 | Streamlit dashboard — run the full pipeline from the browser | ✅ Complete |
| 6 | Application tracker — SQLite database | 🔜 Planned |
| 7 | Expanded search — additional job source integrations | 🔜 Planned |

---

## About

Built by **Jason W. Darrow** — IT Delivery Manager, US Air Force Veteran, BJJ Black Belt, and currently very much learning AI by doing.

- 🌐 [jasondarrow.com](https://jasondarrow.com)
- 💼 [linkedin.com/in/jason-w-darrow](https://linkedin.com/in/jason-w-darrow)
- 🐙 [github.com/darrowj](https://github.com/darrowj)