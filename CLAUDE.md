# CLAUDE.md — AI Job Search Project Primer

> This file is a session primer for Claude (Cowork). Read this at the start of every session to restore full context on Jason's job search project. Jason will prompt Claude to update this file before ending each session.

---

## Who is Jason

**Jason W. Darrow** — IT Delivery Manager, US Air Force Veteran, BJJ Black Belt, currently based in Milford, MA.

- 15+ years IT delivery and program management experience
- 17+ years financial services background (Voya Financial, Bank of America)
- PMP and CSM certified
- Currently employed at Voya Financial as IT Delivery Manager (October 2018 – Present)
- Learning AI by building — this project is the proof

**Contact:**
- Email: Jason@JasonDarrow.com | darrowj@gmail.com
- Phone: 774-573-8354
- Website: jasondarrow.com
- LinkedIn: linkedin.com/in/jasondarrow
- GitHub: github.com/darrowj

---

## What This Project Is

An AI-powered job search system built by Jason to find roles, enrich company intelligence, tailor resumes to specific job postings, and track applications — while simultaneously demonstrating AI engineering skills to prospective employers.

**Two goals at once:** Find a job. Build a portfolio that shows he can build AI tools.

Live portfolio: [jasondarrow.com](https://jasondarrow.com)
GitHub: [github.com/darrowj/ai-job-search](https://github.com/darrowj/ai-job-search)

---

## Project Architecture

### The Workflow
```
1. job_scraper.py        → Searches Adzuna API by title/location → Excel file
2. Manual review         → Mark interesting roles as "Interested" in Excel
3. enrich_jobs.py        → Pulls company intel (Wikipedia, NewsAPI) for Interested rows
4. report_generator.py   → Generates HTML report with company briefs + tailor commands
5. resume_tailor.py      → Reads job URL, uses Claude API to select best bullets from master DB
6. resume_generator.py   → Outputs submission-ready .docx resume
7. Human review          → Edit, export to PDF, submit
```

### Key Files
| File | Purpose |
|------|---------|
| `master_resume.json` | 53-bullet career database with tags and strength scores (1–10) |
| `resume_tailor.py` | Claude API integration — selects bullets, rewrites summary |
| `resume_generator.py` | python-docx Word doc generation |
| `job_scraper.py` | Adzuna API job search → Excel |
| `enrich_jobs.py` | Company intelligence enrichment |
| `report_generator.py` | HTML job report generation |
| `.env` | API keys (never committed) |

### Tech Stack
Python 3 · Claude API · Adzuna API · NewsAPI · Wikipedia API · python-docx · pandas · openpyxl · BeautifulSoup · GitHub · AWS S3 + Route 53

---

## Master Resume Structure

Jason's resume is a **database of 53 bullets** tagged by skill category and scored by strength (1–10). The AI selects the best 5–6 bullets per role rather than showing everything.

**Three summary profiles:**
- `delivery-mgr` — IT Delivery Manager / Program Manager (primary target)
- `ai-transformation` — AI / Digital Transformation / Technology Leadership
- `technical-mgr` — Technical Manager / Engineering Manager

**Key career highlights:**
- Led IT programs $250K–$3M, coordinating 30+ application teams
- Managed onshore and offshore vendor + FTE blended teams
- Served as face of IT for senior business stakeholders
- Architect/Developer for aircraft residual calculator supporting $1.2B in business (Bank of America)
- Technical lead for bankofamericaleasing.com ($32B managed assets)

---

## Project Status

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

## Job Search Status

- **Active target roles:** IT Delivery Manager, Program Manager (primary); AI/Digital Transformation, consulting/contract roles (secondary)
- **Target locations:** Boston MA, Worcester MA area
- **Salary floor:** $120k+. Stored privately in `.env` as `MIN_SALARY` — not committed to GitHub
- **Employment preference:** Contract/consulting (6-month), open to hybrid 3 days/week, 5 days if money is right
- **Applications submitted:** None yet — laid off 5/4, last day 6/15, severance ~$120k pre-tax
- **Interview activity:** None yet — plans to start telling close contacts week of 5/19
- **LinkedIn:** 305 real connections (quality over quantity). Not yet active posting.
- **Networking:** Plans to resume local networking events (did 2-3/month during 2018 search)

---

## Claude's Role in This Project

Jason has asked Claude to act as a combined **career mentor + job search strategist + grizzled HR veteran of 20 years**. This means:

- Give honest, direct feedback — not just validation
- Push back when priorities seem off
- Think about real-world hiring outcomes, not just code quality
- Balance technical project work with actual job search effectiveness
- Ask hard questions: Are you getting interviews? What's the response rate? Is the tool serving the search?

---

## Strategic Direction

- **Dual track:** Active job search (contract/consulting priority) in parallel with building 3-4 AI portfolio projects
- **Portfolio projects planned:**
  - #1 — AI Job Search System (this project — complete)
  - #2 — Stock options research/strategy AI tool (highest portfolio value for FinTech employers)
  - #3 — Shooting match finder (practiscore.com scraper for USPSA/IDPA/NRL22/PRS Rimfire/Steel Challenge)
  - #4 — TBD
- **Freelance/consulting aspiration:** Build AI-powered apps for SMBs. Best year moonlighting was $40k — needs to scale
- **Wife is supportive.** Retirement is technically on the table (Rule of 55, ~$1.3M retirement savings, $5k/month expenses, wife carries health insurance)

## Open Questions / Next Steps

- Start personal network outreach week of 5/19 — know what you're asking for before you call
- Get active on LinkedIn — 2-3 posts/week about what you're building
- Rotate API keys exposed in Cowork session on 5/17
- Wave 5 (application tracker) still planned but not urgent yet
- Cover letter generation — not yet built, potentially high value
- Interview prep support — not yet discussed

---

## Session Log

| Date | What We Did |
|------|-------------|
| 2026-05-17 | First full session. Read all project files. Established career mentor + HR veteran role. Discussed job search situation, financial runway, Churchill/autonomy question, dual-track strategy. Improved job_scraper.py: added search_config.json with _comment documentation, title allowlist filter (replaced blocklist), min_salary moved to .env, max_days_old filter, job_type filter. Updated .gitignore to exclude output files and Mac/Python junk. Created this CLAUDE.md. |

---

*Last updated: 2026-05-17*
