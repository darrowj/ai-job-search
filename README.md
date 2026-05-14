# AI Job Search System
### Built by Jason Darrow | [jasondarrow.com](https://jasondarrow.com)

An AI-powered job search assistant that finds relevant job postings, enriches them with company intelligence, customizes my resume and cover letter for each role using the Claude API, and tracks my application progress from submission to offer.

Built as a hands-on learning project to develop real AI engineering skills while solving a real personal problem — finding a job.

---

## What it does

- **Scrapes job boards** across multiple titles and locations via the Adzuna API — outputs to a dated Excel file
- **Enriches listings** with company intelligence — industry, size, stability, growth trend, and recent news via Wikipedia and NewsAPI
- **Generates an HTML report** of shortlisted jobs with company briefs and one-click resume tailor commands
- **Tailors resumes** using the Claude API — reads a real job posting URL, selects the best matching bullets from a 53-bullet master resume database, rewrites the summary to match
- **Generates Word documents** — reconstructs my resume format with AI-selected bullets, outputs a submission-ready .docx file
- **Portfolio site** live at [jasondarrow.com](https://jasondarrow.com) documenting the project and journey

---

## The workflow

```
1. python3 job_scraper.py --titles "IT Delivery Manager" "Program Manager" \
                          --locations "Boston MA" "Worcester MA"
   → job_listings_2026-05-14.xlsx

2. Open Excel → mark interesting roles as "Interested"

3. python3 enrich_jobs.py
   → pulls company intel for Interested rows
   → generates job_report_2026-05-14.html

4. Open HTML report in browser
   → read company briefs
   → copy tailor command for roles you want to apply to

5. python3 resume_tailor.py --company "Fidelity" \
                             --title "Technical Project Delivery Manager" \
                             --url "https://linkedin.com/jobs/..."
   → tailored_Fidelity.json (match score, selected bullets)

6. python3 resume_generator.py --input tailored_Fidelity.json
   → Jason_Darrow_Resume.docx

7. Review, edit, export to PDF, submit
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
job_scraper.py          Search job boards, output to Excel
enrich_jobs.py          Enrich Interested listings with company intel
report_generator.py     Generate HTML report from enriched listings
resume_tailor.py        AI resume tailoring via Claude API
resume_generator.py     Generate Word doc from tailored JSON
master_resume.json      53-bullet career database with tags and strength scores
index.html              Portfolio site source
```

---

## Key design decisions

**Master resume as a database** — instead of one static resume, all career experience lives in a JSON file with 53 bullets tagged by skill category and scored by strength. The AI selects the best 5-6 per role rather than showing everything.

**Iterative waves** — built in waves (0-4) so each phase produces something useful before moving to the next. No big bang releases.

**Secrets management** — all API keys in `.env`, never committed to GitHub.

**Human in the loop** — Claude selects and adjusts bullets but never invents experience. Every generated resume is reviewed and edited before submission.

---

## Setup

```bash
# Clone the repo
git clone https://github.com/darrowj/ai-job-search.git
cd ai-job-search

# Install dependencies
pip3 install anthropic requests beautifulsoup4 python-dotenv \
             pandas openpyxl python-docx

# Add your API keys to .env
ANTHROPIC_API_KEY=your_key
ADZUNA_APP_ID=your_id
ADZUNA_APP_KEY=your_key
NEWS_API_KEY=your_key

# Run the scraper
python3 job_scraper.py --titles "IT Delivery Manager" --locations "Boston MA"
```

---

## Project status

| Wave | Description | Status |
|------|-------------|--------|
| 0 | Master resume JSON database | ✅ Complete |
| 1 | Job scraper — Adzuna API, Excel output | ✅ Complete |
| 2 | AI resume tailoring + Word doc generation | ✅ Complete |
| 2.5 | Company intelligence enrichment | ✅ Complete |
| 3 | HTML job report | ✅ Complete |
| 4 | Portfolio site — jasondarrow.com | ✅ Complete |
| 5 | Application tracker — SQLite database | 🔜 Planned |
| 6 | SerpAPI integration for fresher listings | 🔜 Planned |

---

## About

Built by **Jason W. Darrow** — IT Delivery Manager, US Air Force Veteran, BJJ Black Belt, and currently very much learning AI by doing.

- 🌐 [jasondarrow.com](https://jasondarrow.com)
- 💼 [linkedin.com/in/jason-w-darrow](https://linkedin.com/in/jason-w-darrow)
- 🐙 [github.com/darrowj](https://github.com/darrowj)