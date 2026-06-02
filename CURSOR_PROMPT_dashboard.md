# Cursor Build Prompt — Streamlit Dashboard for AI Job Search

Paste everything below into Cursor (Composer/Agent mode, with the repo open).  Build incrementally and run after each phase.

---

## Context for the AI

You are adding a **Streamlit dashboard** (`dashboard.py`) to an existing Python job-search pipeline.  Do NOT rewrite the existing scripts' logic.  The dashboard is a review-and-launch layer on top of scripts that already work.

### Existing pipeline (do not break these)
- `job_scraper.py` — searches Adzuna, writes an Excel file to `output/`
- `enrich_jobs.py` — reads rows marked `Interested` in the Excel, adds company intel
- `report_generator.py` — builds an HTML report from enriched data
- `resume_tailor.py` — selects bullets from `master_resume.json` for one job, writes `output/tailored_COMPANY.json`
- `resume_generator.py` — `--input output/tailored_COMPANY.json` → writes a `.docx` to `personal/`

### Folder rules
- Generated pipeline files live in `output/` (gitignored)
- Resumes and personal docs live in `personal/` (gitignored)
- API keys live in `.env` — never read or print them in the dashboard
- Use `os.makedirs(..., exist_ok=True)` guards, matching the existing scripts

### Tech constraints
- Python 3, Streamlit, pandas, openpyxl (already in use)
- Add `streamlit` to `requirements.txt`
- Run scripts with `subprocess.Popen` and **stream stdout live** — never block the UI with `subprocess.run`
- The dashboard PULLS state by reading `output/` files; it does not track API calls directly
- Single-user, local only.  No auth, no database (the SQLite tracker is a later wave)

---

## What to build: `dashboard.py`

A Streamlit app organized as **5 tabs**, one per pipeline stage.  Use `st.session_state` to remember progress (last run status, selected job) across Streamlit's automatic reruns.

### Shared helper: streaming subprocess runner
Write one reusable function used by every "Run" button:

```python
def run_script(cmd: list[str]) -> int:
    """Run a script, stream stdout live into the page, return exit code."""
    log_box = st.empty()
    lines = []
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    for line in proc.stdout:
        lines.append(line)
        log_box.code("".join(lines[-200:]))  # show last 200 lines
    proc.wait()
    return proc.returncode
```

Show `st.success` on exit code 0, `st.error` otherwise.

### Top of page: status panel
Above the tabs, render a status bar that reads the current `output/` Excel (handle the file-not-found case gracefully):
- Last run timestamp = file modification time of the job Excel
- Metrics via `st.metric`: total jobs, # Interested, # enriched, # resumes tailored (count `output/tailored_*.json`)
- A "Refresh" note (Streamlit reruns on any interaction)

> NOTE: the existing scripts have a filename mismatch — `job_scraper.py` writes a dated name like `job_listings_YYYY-MM-DD.xlsx` while `enrich_jobs.py` defaults to `output/job_listings.xlsx`.  In the dashboard, define a single constant `JOB_FILE = "output/job_listings.xlsx"` and use it everywhere.  If the scraper still writes a dated file, after a scrape completes, copy/rename the newest `output/job_listings*.xlsx` to `JOB_FILE` so the rest of the pipeline lines up.  Add a `# TODO` comment recommending the scraper default be changed to the undated name.

### Tab 1 — Scrape
- A "Run Scraper" button → `run_script(["python3", "job_scraper.py"])`
- Live log via the helper
- On completion, normalize the output filename to `JOB_FILE` (see note above) and show new row count

### Tab 2 — Review & Mark Interest
- Load `JOB_FILE` into `st.data_editor`
- Make `Status` an editable `SelectboxColumn` with options `["", "Interested", "Skip"]`
- Show key columns prominently (Title, Company, Location, Salary, URL); make URL a `LinkColumn` if present
- A "Save selections" button writes the edited dataframe back to `JOB_FILE` with `to_excel(..., index=False)` and reports how many are now `Interested`
- This replaces editing the Excel by hand

### Tab 3 — Enrich
- Compute `interested = df[df.Status == "Interested"]` from `JOB_FILE`
- Show count.  Only enable the "Enrich Interested Jobs" button when count > 0
- Button → `run_script(["python3", "enrich_jobs.py"])`, live log
- After it runs, display the enriched company briefs.  Read whatever `enrich_jobs.py` outputs (enriched Excel and/or the HTML report).  Render briefs in `st.expander` blocks, one per company, so Jason can read about each
- Add a "Generate HTML Report" button → `run_script(["python3", "report_generator.py"])` and a link to open the generated HTML in `output/`

### Tab 4 — Tailor Resume
- `st.selectbox` to pick ONE company from the Interested list
- "Tailor Resume" button → `run_script(["python3", "resume_tailor.py", <args>])`
  - Inspect `resume_tailor.py`'s actual CLI args and pass them correctly (it may take a URL or company).  If it currently only takes a URL and the Adzuna page is JS-rendered (known issue returning ~17 chars), add a `st.text_area` fallback where Jason can paste the job description, save it to a temp file, and pass that to the tailor step.  Add a `# TODO` noting the URL-fetch fix
- Show the match score / selected bullets from `output/tailored_COMPANY.json` after it runs
- "Generate Word Doc" button → `run_script(["python3", "resume_generator.py", "--input", f"output/tailored_{company}.json"])`
- After generation, provide a `st.download_button` for the resulting `.docx` in `personal/`

### Tab 5 — Status / Tracker (lightweight for now)
- A read-only table summarizing the current run: each Interested job, whether it's been enriched, whether a tailored resume exists (`output/tailored_<company>.json` present?), whether a `.docx` exists
- This is the seed of the future SQLite application tracker — keep it simple, just derive from files on disk

---

## Session state requirements
Use `st.session_state` to persist across reruns:
- `selected_company` (Tab 4 dropdown choice)
- last run results / messages per stage
- so moving between tabs doesn't lose context

## Print-statement additions (do this too)
For the live logs to be useful, add concise `print(..., flush=True)` statements to the existing scripts at these points (keep them, they help CLI use too):
- `job_scraper.py`: before each search query, after each, and final count + output path
- `enrich_jobs.py`: before enriching each company ("Enriching {company} via NewsAPI/Wikipedia..."), after, and final summary
- `resume_tailor.py`: which job, match score, bullets selected, output path
- `resume_generator.py`: input file, output `.docx` path
Use `flush=True` so Streamlit sees lines immediately.

## Deliverables
1. `dashboard.py` at repo root
2. `streamlit` added to `requirements.txt`
3. `print(..., flush=True)` additions in the four scripts noted above
4. A short `## Dashboard` section in `README.md`: how to launch (`streamlit run dashboard.py`), what each tab does, and a note that it's the human-in-the-loop control panel for the pipeline
5. Inline `# TODO` comments for: scraper filename default, resume_tailor URL-fetch fix

## Acceptance test
- `streamlit run dashboard.py` opens without error
- Status panel renders even when `output/` is empty (no crash on missing files)
- Each tab's Run button streams live log output and reports success/failure
- Editing Status in Tab 2 and saving updates `JOB_FILE`; Tab 3 then sees the Interested rows
- Tailoring produces a `.docx` that downloads from Tab 4

Build Tab 1 + the status panel + the `run_script` helper first.  Confirm it runs.  Then add tabs 2–5 one at a time.
