"""Streamlit control panel for the AI job search pipeline.

Six tabs map to pipeline stages and scripts:
    1. Scrape        → job_scraper.py
    2. Review        → edit Status in the Excel
    3. Enrich        → enrich_jobs.py + report_generator.py
    4. Tailor        → resume_tailor.py + resume_generator.py (+ cover letter shortcut)
    5. Status        → file-derived tracker (seed for the future SQLite tracker)
    6. Cover Letter  → cover_letter_generator.py (standalone)

The dashboard never reads .env directly — keys stay where they belong.
It also never duplicates pipeline logic; every action is a subprocess call
to an existing script with stdout streamed live into the page.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import webbrowser
from datetime import date as _date
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

# ── Paths and constants ────────────────────────────────────────────────────

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "output"
ARCHIVE_DIR = OUTPUT_DIR / "archive"
PERSONAL_DIR = HERE / "personal"

# Canonical Excel used by every tab. job_scraper.py writes here directly and
# archives a dated copy under output/archive/ (not read by the pipeline).
JOB_FILE = OUTPUT_DIR / "job_listings.xlsx"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)
os.makedirs(PERSONAL_DIR, exist_ok=True)

# ── Streaming subprocess helper ────────────────────────────────────────────

def run_script(cmd: list[str]) -> int:
    """Run a script, stream stdout live into the page, return exit code."""
    log_box = st.empty()
    lines: list[str] = []
    # PYTHONUNBUFFERED is belt-and-suspenders; the scripts themselves use
    # flush=True, but this catches any stragglers (e.g. stderr from libs).
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(HERE),
        env=env,
    )
    assert proc.stdout is not None  # for type checker
    for line in proc.stdout:
        lines.append(line)
        log_box.code("".join(lines[-200:]))  # show last 200 lines
    proc.wait()
    if proc.returncode == 0:
        st.success(f"Finished: {' '.join(cmd)}")
    else:
        st.error(f"Exit code {proc.returncode}: {' '.join(cmd)}")
    return proc.returncode


# ── File helpers ───────────────────────────────────────────────────────────

ARCHIVE_LISTING_RE = re.compile(r"^job_listings_(\d{4}-\d{2}-\d{2})\.xlsx$")
REPORT_DATE_RE = re.compile(r"^job_report_(\d{4}-\d{2}-\d{2})\.html$")


def _is_lock_file(path: Path) -> bool:
    """Excel and Word write `~$name` lock files — never treat them as data."""
    return path.name.startswith("~$")


def _parse_filename_date(path: Path, pattern: re.Pattern) -> Optional[_date]:
    m = pattern.match(path.name)
    if not m:
        return None
    try:
        return _date.fromisoformat(m.group(1))
    except ValueError:
        return None


def list_archived_scrapes() -> list[tuple[_date, Path]]:
    """Dated scrape snapshots under output/archive/, newest first."""
    entries: list[tuple[_date, Path]] = []
    if not ARCHIVE_DIR.exists():
        return entries
    for p in ARCHIVE_DIR.glob("job_listings_*.xlsx"):
        if _is_lock_file(p):
            continue
        d = _parse_filename_date(p, ARCHIVE_LISTING_RE)
        if d is not None:
            entries.append((d, p))
    entries.sort(key=lambda x: x[0], reverse=True)
    return entries


def find_newest_dated_report() -> tuple[Optional[Path], Optional[_date]]:
    """Return (path, date) for the newest job_report_YYYY-MM-DD.html by filename date."""
    best: tuple[Optional[Path], Optional[_date]] = (None, None)
    for p in OUTPUT_DIR.glob("job_report_*.html"):
        if _is_lock_file(p):
            continue
        d = _parse_filename_date(p, REPORT_DATE_RE)
        if d is None:
            continue
        if best[1] is None or d > best[1]:
            best = (p, d)
    return best


def load_job_df() -> Optional[pd.DataFrame]:
    """Read the canonical Excel; return None gracefully if missing or unreadable."""
    if not JOB_FILE.exists():
        return None
    try:
        return pd.read_excel(JOB_FILE)
    except Exception as e:  # noqa: BLE001
        st.warning(f"Could not read {JOB_FILE.name}: {e}")
        return None


def save_job_df(df: pd.DataFrame) -> None:
    df.to_excel(JOB_FILE, index=False, engine="openpyxl")


def count_tailored() -> int:
    return len(list(OUTPUT_DIR.glob("tailored_*.json")))


def safe_company_slug(name: str) -> str:
    return (name or "").strip().replace(" ", "_")


# ── Session state ──────────────────────────────────────────────────────────

def _init_state() -> None:
    defaults = {
        "selected_company": None,
        "stage_messages": {},   # stage_name -> human-readable last result
        "last_tailor_company": None,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


# ── Page setup ─────────────────────────────────────────────────────────────

st.set_page_config(page_title="Job Search Dashboard", layout="wide")
_init_state()

st.title("Job Search Dashboard")
st.caption("Human-in-the-loop control panel for the AI job search pipeline.")


# ── Status panel ───────────────────────────────────────────────────────────

def render_status_panel() -> None:
    df = load_job_df()

    if df is None:
        st.info(f"No `{JOB_FILE.relative_to(HERE)}` yet — run the scraper in **Tab 1** to begin.")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total jobs", 0)
        c2.metric("Interested", 0)
        c3.metric("Enriched", 0)
        c4.metric("Resumes tailored", count_tailored())
        return

    total = len(df)
    status_series = df["Status"].astype(str).str.strip().str.lower() if "Status" in df.columns else pd.Series([], dtype=str)
    interested_mask = status_series == "interested"
    interested = int(interested_mask.sum())

    if "Industry" in df.columns and interested:
        enriched = int(
            (df.loc[interested_mask, "Industry"].astype(str).str.strip() != "").sum()
        )
    else:
        enriched = 0

    last_modified = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(JOB_FILE.stat().st_mtime))
    st.caption(
        f"Source: `{JOB_FILE.relative_to(HERE)}` · "
        f"last modified **{last_modified}**"
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total jobs", total)
    c2.metric("Interested", interested)
    c3.metric("Enriched", enriched)
    c4.metric("Resumes tailored", count_tailored())


render_status_panel()
st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "1. Scrape",
    "2. Review",
    "3. Enrich",
    "4. Tailor",
    "5. Status",
    "6. Cover Letter",
])

# ── Tab 1: Scrape ──────────────────────────────────────────────────────────

with tab1:
    st.subheader("Run the scraper")
    st.write(
        "Reads `search_config.json`, queries JSearch (OpenWeb Ninja), and writes "
        f"`{JOB_FILE.relative_to(HERE)}`. "
        "A dated snapshot is also saved under `output/archive/`."
    )

    if st.button("Run Scraper", type="primary", key="run_scraper"):
        rc = run_script(["python3", "job_scraper.py"])
        if rc == 0 and JOB_FILE.exists():
            df_after = load_job_df()
            rows = 0 if df_after is None else len(df_after)
            st.success(f"Saved `{JOB_FILE.relative_to(HERE)}` with **{rows}** rows.")
            st.session_state.stage_messages["scrape"] = f"{rows} rows"
        elif rc == 0:
            st.warning("Scraper finished but no job listings file was found.")

    archived = list_archived_scrapes()
    if archived:
        with st.expander(f"Archived scrapes ({len(archived)})"):
            for d, p in archived:
                size_kb = p.stat().st_size // 1024
                st.write(f"- `{p.relative_to(HERE)}` · {d.isoformat()} · {size_kb} KB")

    if "scrape" in st.session_state.stage_messages:
        st.caption(f"Last scrape: {st.session_state.stage_messages['scrape']}")


# ── Tab 2: Review & Mark Interest ──────────────────────────────────────────

with tab2:
    st.subheader("Review and mark interest")
    df = load_job_df()
    if df is None:
        st.info("Run the scraper first (Tab 1).")
    else:
        # Ensure Status exists; coerce unknown statuses (e.g. legacy "New") to ""
        # so the SelectboxColumn options match the spec exactly.
        if "Status" not in df.columns:
            df["Status"] = ""
        df["Status"] = df["Status"].fillna("").astype(str).str.strip()
        status_options = ["", "Interested", "Skip"]
        df["Status"] = df["Status"].where(df["Status"].isin(status_options), "")

        # Reorder so Jason sees the most useful columns first.
        priority = [c for c in ["Title", "Company", "Location", "Salary", "Apply URL", "Status"] if c in df.columns]
        rest = [c for c in df.columns if c not in priority]
        view = df[priority + rest]

        column_config = {
            "Status": st.column_config.SelectboxColumn(
                "Status", options=status_options, required=False,
            ),
        }
        if "Apply URL" in view.columns:
            column_config["Apply URL"] = st.column_config.LinkColumn("Apply URL")

        edited = st.data_editor(
            view,
            column_config=column_config,
            num_rows="fixed",
            width="stretch",
            hide_index=True,
            key="review_editor",
        )

        if st.button("Save selections", type="primary", key="save_selections"):
            save_job_df(edited)
            n_interested = int(
                (edited["Status"].astype(str).str.strip().str.lower() == "interested").sum()
            )
            st.success(f"Saved. **{n_interested}** job(s) now marked Interested.")
            st.session_state.stage_messages["review"] = f"{n_interested} interested"


# ── Tab 3: Enrich ──────────────────────────────────────────────────────────

with tab3:
    st.subheader("Enrich Interested jobs")
    df = load_job_df()
    if df is None:
        st.info("No job file yet — scrape first (Tab 1).")
    else:
        if "Status" not in df.columns:
            df["Status"] = ""
        interested_mask = df["Status"].astype(str).str.strip().str.lower() == "interested"
        interested_count = int(interested_mask.sum())

        st.metric("Interested jobs ready to enrich", interested_count)

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button(
                "Enrich Interested Jobs (Step 1)",
                type="primary",
                disabled=interested_count == 0,
                key="run_enrich",
            ):
                run_script(["python3", "enrich_jobs.py"])
                st.session_state.stage_messages["enrich"] = "enrichment run complete"

        with col_b:
            if st.button(
                "Generate HTML Report (Step 2)",
                type="primary",
                key="run_report",
            ):
                report_path = OUTPUT_DIR / f"job_report_{time.strftime('%Y-%m-%d')}.html"
                run_script([
                    "python3", "report_generator.py",
                    "--output", str(report_path),
                ])

        # Reload after potential run, then show the briefs.
        df = load_job_df()
        if df is not None and "Industry" in df.columns:
            interested_now = df[
                df["Status"].astype(str).str.strip().str.lower() == "interested"
            ]
            enriched_rows = interested_now[
                interested_now["Industry"].astype(str).str.strip() != ""
            ]
            if len(enriched_rows):
                st.markdown("### Company briefs")
                for _, row in enriched_rows.iterrows():
                    company = row.get("Company", "(unknown)")
                    title = row.get("Title", "")
                    industry = str(row.get("Industry", "") or "")
                    hq = str(row.get("HQ Location", "") or "")
                    size = str(row.get("Company Size", "") or "")
                    desc = str(row.get("Description", "") or "")
                    rec = str(row.get("Recommendation", "") or "")
                    stability = str(row.get("Stability", "") or "")
                    growth = str(row.get("Growth Trend", "") or "")
                    with st.expander(f"{company} — {title}"):
                        meta_bits = [m for m in [industry, hq, size] if m]
                        if meta_bits:
                            st.write(" · ".join(meta_bits))
                        if stability or growth:
                            st.caption(f"Stability: {stability or '—'}  ·  Growth trend: {growth or '—'}")
                        if desc:
                            st.write(desc)
                        if rec:
                            st.markdown(f"> **Recommendation:** {rec}")

        # Latest HTML report download / link — picked by filename date
        # (job_report_YYYY-MM-DD.html) so this stays consistent with how the
        # report_generator names its output. mtime would lie if any old report
        # gets touched.
        report_path, report_date = find_newest_dated_report()
        if report_path is not None:
            today = _date.today()
            date_str = report_date.isoformat() if report_date else "unknown"
            tag = " (today)" if report_date == today else ""
            st.caption(f"Latest report file: `{report_path.relative_to(HERE)}` · date: **{date_str}**{tag}")
            if report_date and report_date < today:
                st.info(
                    "This report is from an earlier day. Click **Generate HTML Report** "
                    "above to produce one for today."
                )
            col_dl, col_open = st.columns(2)
            with col_dl:
                with report_path.open("rb") as f:
                    st.download_button(
                        "Download latest HTML report",
                        data=f.read(),
                        file_name=report_path.name,
                        mime="text/html",
                    )
            with col_open:
                if st.button("Open in Browser", key="open_report_browser"):
                    webbrowser.open(report_path.resolve().as_uri())


# ── Tab 4: Tailor Resume ──────────────────────────────────────────────────

with tab4:
    st.subheader("Tailor a resume for a single role")
    df = load_job_df()
    if df is None:
        st.info("No job file yet — scrape first (Tab 1).")
    else:
        if "Status" not in df.columns:
            df["Status"] = ""
        interested = df[
            df["Status"].astype(str).str.strip().str.lower() == "interested"
        ].copy().reset_index(drop=True)

        if len(interested) == 0:
            st.info("Mark some jobs as Interested in Tab 2 first.")
        else:
            # Build labels for the dropdown; keep Company in session for memory across tabs.
            labels = [
                f"{r.get('Company', '(unknown)')} — {r.get('Title', '')}".strip(" —")
                for _, r in interested.iterrows()
            ]
            companies = [str(c) for c in interested["Company"].fillna("").astype(str).tolist()]

            default_idx = 0
            if st.session_state.selected_company in companies:
                default_idx = companies.index(st.session_state.selected_company)

            chosen_label = st.selectbox(
                "Pick an Interested role",
                labels,
                index=default_idx,
                key="tailor_company_pick",
            )
            row = interested.iloc[labels.index(chosen_label)]
            company = str(row["Company"]).strip()
            title = str(row.get("Title", "")).strip() or "Position"
            url = str(row.get("Apply URL", "")).strip()
            st.session_state.selected_company = company

            # JSearch now stores the full posting in the "Job Description"
            # column, so most roles are hands-free: pick the role and the
            # description below auto-fills, then it's passed straight to both
            # resume_tailor.py and cover_letter_generator.py via --description.
            # The textarea stays editable and is the fallback for any role that
            # was scraped without a description.
            raw_jd = row.get("Job Description", "")
            try:
                jd_is_blank = bool(pd.isna(raw_jd))
            except (TypeError, ValueError):
                jd_is_blank = False
            excel_jd = "" if jd_is_blank else str(raw_jd).strip()

            # Seed the textarea from the Excel description whenever the selected
            # role changes. Setting the widget's session_state value *before*
            # the widget is created is the supported way to programmatically
            # populate it; guarding on the label keeps later manual edits.
            ta_key = "tailor_jd_textarea"
            if st.session_state.get("jd_loaded_for") != chosen_label:
                st.session_state[ta_key] = excel_jd
                st.session_state["jd_loaded_for"] = chosen_label

            if excel_jd:
                st.caption("Job description auto-filled from the scraped Excel. Edit if needed.")
            else:
                st.caption("No description was scraped for this role — paste one below.")
            if url:
                st.caption(f"Posting: [{url}]({url})")

            jd_text = st.text_area(
                "Job description (used for both the resume and cover letter)",
                key=ta_key,
                height=240,
            )
            jd_clean = jd_text.strip()

            cmd = ["python3", "resume_tailor.py", "--company", company, "--title", title]
            if jd_clean:
                cmd += ["--description", jd_clean]

            ready = bool(jd_clean)
            if not ready:
                st.warning("Provide a job description above to tailor the resume.")

            if st.button("Tailor Resume", type="primary", disabled=not ready, key="run_tailor"):
                run_script(cmd)
                st.session_state.last_tailor_company = company

            # Show tailored output if it exists for the selected company.
            slug = safe_company_slug(company)
            tailored_path = OUTPUT_DIR / f"tailored_{slug}.json"
            if tailored_path.exists():
                try:
                    data = json.loads(tailored_path.read_text())
                except Exception as e:  # noqa: BLE001
                    st.error(f"Could not read {tailored_path.name}: {e}")
                    data = {}

                st.markdown(f"### Tailored output — **{company}**")
                score = data.get("match_score")
                if score is not None:
                    st.metric("Match score", f"{score} / 100")
                key_skills = data.get("key_skills") or []
                if key_skills:
                    st.write("**Key skills selected:** " + ", ".join(key_skills))
                summary = data.get("tailored_summary") or ""
                if summary:
                    with st.expander("Tailored summary"):
                        st.write(summary)
                bullets = data.get("selected_bullets") or []
                if bullets:
                    with st.expander(f"Selected bullets ({len(bullets)})"):
                        for b in bullets:
                            st.markdown(
                                f"- *{b.get('company','')} — {b.get('title','')}* — "
                                f"{b.get('bullet','')}"
                            )

                docx_path = PERSONAL_DIR / f"Jason_Darrow_Resume_{slug}.docx"
                col_g, col_d = st.columns(2)
                with col_g:
                    if st.button("Generate Word Doc", key="run_resume_gen"):
                        run_script([
                            "python3", "resume_generator.py",
                            "--input", str(tailored_path.relative_to(HERE)),
                            "--output", str(docx_path.relative_to(HERE)),
                        ])
                with col_d:
                    if docx_path.exists():
                        with docx_path.open("rb") as f:
                            st.download_button(
                                f"Download {docx_path.name}",
                                data=f.read(),
                                file_name=docx_path.name,
                                mime=(
                                    "application/vnd.openxmlformats-"
                                    "officedocument.wordprocessingml.document"
                                ),
                            )
                    else:
                        st.caption("Generate the Word doc to enable download.")

                # ── Cover letter ──────────────────────────────────────────
                st.divider()
                st.markdown("#### Cover Letter")
                st.caption(
                    "Uses the same job description above (auto-filled from the "
                    "scraped Excel when available) plus the tailored bullet "
                    "selection for this role."
                )

                cl_path = PERSONAL_DIR / f"CoverLetter_{slug}.docx"
                col_cl, col_cld = st.columns(2)
                jd_for_cl = jd_clean
                with col_cl:
                    cl_ready = bool(jd_for_cl)
                    if not cl_ready:
                        st.caption("Provide a job description above to enable cover letter generation.")
                    if st.button(
                        "Generate Cover Letter",
                        key="run_cover_letter",
                        disabled=not cl_ready,
                    ):
                        run_script([
                            "python3", "cover_letter_generator.py",
                            "--company",     company,
                            "--title",       title,
                            "--description", jd_for_cl,
                            "--input",       str(tailored_path.relative_to(HERE)),
                            "--output",      str(cl_path.relative_to(HERE)),
                        ])
                with col_cld:
                    if cl_path.exists():
                        with cl_path.open("rb") as f:
                            st.download_button(
                                f"Download {cl_path.name}",
                                data=f.read(),
                                file_name=cl_path.name,
                                mime=(
                                    "application/vnd.openxmlformats-"
                                    "officedocument.wordprocessingml.document"
                                ),
                            )
                    else:
                        st.caption("Generate the cover letter to enable download.")


# ── Tab 5: Status / Tracker ───────────────────────────────────────────────

with tab5:
    st.subheader("Pipeline status")
    st.caption(
        "Lightweight tracker derived from files on disk. "
        "Wave 7 will replace this with a full application tracker."
    )
    df = load_job_df()
    if df is None:
        st.info("No job file yet — scrape first (Tab 1).")
    else:
        if "Status" not in df.columns:
            df["Status"] = ""
        interested = df[
            df["Status"].astype(str).str.strip().str.lower() == "interested"
        ].copy()
        if len(interested) == 0:
            st.info("No Interested jobs to track. Mark some in Tab 2.")
        else:
            rows = []
            for _, r in interested.iterrows():
                company = str(r.get("Company", "")).strip()
                slug = safe_company_slug(company)
                tailored_exists = (OUTPUT_DIR / f"tailored_{slug}.json").exists()
                docx_exists = (PERSONAL_DIR / f"Jason_Darrow_Resume_{slug}.docx").exists()
                cl_exists = (PERSONAL_DIR / f"CoverLetter_{slug}.docx").exists()
                enriched = (
                    bool(str(r.get("Industry", "") or "").strip())
                    if "Industry" in df.columns else False
                )
                match_raw = r.get("Match Score", "")
                match_score = str(match_raw).strip()
                if match_score.lower() == "nan":
                    match_score = ""
                elif match_score:
                    # Drop pandas float artifacts so 85.0 displays as 85.
                    try:
                        match_score = str(int(float(match_score)))
                    except ValueError:
                        pass
                rows.append({
                    "Company": company,
                    "Title": str(r.get("Title", "")),
                    "Enriched": "✅" if enriched else "—",
                    "Tailored": "✅" if tailored_exists else "—",
                    "Resume DOCX": "✅" if docx_exists else "—",
                    "Cover Letter": "✅" if cl_exists else "—",
                    "Match Score": f"{match_score}%" if match_score else "—",
                })
            st.dataframe(
                pd.DataFrame(rows),
                width="stretch",
                hide_index=True,
            )


# ── Tab 6: Cover Letter ───────────────────────────────────────────────────

with tab6:
    st.subheader("Generate a cover letter")
    st.caption(
        "Runs `cover_letter_generator.py` for any role.  Prefill from an Interested "
        "job or enter company, title, and description manually.  If a tailored resume "
        "JSON already exists for this company, it is passed automatically."
    )

    df = load_job_df()
    interested_options: list[str] = [""]
    interested_rows: dict[str, pd.Series] = {}

    if df is not None:
        if "Status" not in df.columns:
            df["Status"] = ""
        interested_cl = df[
            df["Status"].astype(str).str.strip().str.lower() == "interested"
        ].copy()
        for _, r in interested_cl.iterrows():
            label = f"{r.get('Company', '(unknown)')} — {r.get('Title', '')}".strip(" —")
            interested_options.append(label)
            interested_rows[label] = r

    chosen_prefill = st.selectbox(
        "Prefill from Interested role (optional)",
        interested_options,
        format_func=lambda x: "Enter manually" if x == "" else x,
        key="cl_prefill_pick",
    )

    # Seed inputs when the user picks a different Interested role.
    if st.session_state.get("cl_loaded_for") != chosen_prefill:
        if chosen_prefill and chosen_prefill in interested_rows:
            row = interested_rows[chosen_prefill]
            st.session_state["cl_company"] = str(row.get("Company", "")).strip()
            st.session_state["cl_title"] = (
                str(row.get("Title", "")).strip() or "Position"
            )
            raw_jd = row.get("Job Description", "")
            try:
                jd_is_blank = bool(pd.isna(raw_jd))
            except (TypeError, ValueError):
                jd_is_blank = False
            st.session_state["cl_jd_textarea"] = (
                "" if jd_is_blank else str(raw_jd).strip()
            )
        st.session_state["cl_loaded_for"] = chosen_prefill

    company = st.text_input("Company", key="cl_company")
    title = st.text_input("Title", key="cl_title")
    jd_text = st.text_area(
        "Job description",
        key="cl_jd_textarea",
        height=240,
    )
    jd_clean = jd_text.strip()
    company_clean = company.strip()
    title_clean = title.strip()

    cl_ready = bool(company_clean) and bool(title_clean) and len(jd_clean) >= 100
    if not cl_ready:
        if not company_clean or not title_clean:
            st.warning("Company and title are required.")
        elif len(jd_clean) < 100:
            st.warning("Job description must be at least 100 characters.")

    slug = safe_company_slug(company_clean)
    cl_path = PERSONAL_DIR / f"CoverLetter_{slug}.docx"
    tailored_path = OUTPUT_DIR / f"tailored_{slug}.json"

    col_run, col_dl = st.columns(2)
    with col_run:
        if st.button(
            "Generate Cover Letter",
            type="primary",
            disabled=not cl_ready,
            key="run_cover_letter_tab6",
        ):
            cmd = [
                "python3", "cover_letter_generator.py",
                "--company", company_clean,
                "--title", title_clean,
                "--description", jd_clean,
                "--output", str(cl_path.relative_to(HERE)),
            ]
            if tailored_path.exists():
                cmd += ["--input", str(tailored_path.relative_to(HERE))]
            run_script(cmd)
    with col_dl:
        if cl_path.exists() and company_clean:
            with cl_path.open("rb") as f:
                st.download_button(
                    f"Download {cl_path.name}",
                    data=f.read(),
                    file_name=cl_path.name,
                    mime=(
                        "application/vnd.openxmlformats-"
                        "officedocument.wordprocessingml.document"
                    ),
                    key="download_cover_letter_tab6",
                )
        else:
            st.caption("Generate the cover letter to enable download.")

    if tailored_path.exists() and company_clean:
        st.caption(
            f"Tailored resume JSON found — bullet selection from "
            f"`{tailored_path.name}` will be included."
        )
