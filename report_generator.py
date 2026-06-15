#!/usr/bin/env python3
"""Generate a styled HTML job report from job_listings.xlsx (Interested rows only)."""

import argparse
import html
import os
import re
import shlex
from datetime import date
from pathlib import Path

import pandas as pd

COL_TITLE = "Title"
COL_COMPANY = "Company"
COL_LOCATION = "Location"
COL_SALARY = "Salary"
COL_POSTED = "Posted"
COL_TYPE = "Type"
COL_INDUSTRY = "Industry"
COL_SIZE = "Company Size"
COL_HQ = "HQ Location"
COL_FOUNDED = "Founded"
COL_MARKET_CAP = "Market Cap"
COL_DESCRIPTION = "Description"
COL_STABILITY = "Stability"
COL_GROWTH = "Growth Trend"
COL_NEWS = ("News 1", "News 2", "News 3")
COL_NEWS_URL = ("News 1 URL", "News 2 URL", "News 3 URL")
COL_REC = "Recommendation"
COL_ENRICHED_DATE = "Enriched Date"
COL_APPLY = "Apply URL"
COL_STATUS = "Status"
COL_MATCH_SCORE = "Match Score"
COL_MATCH_NOTES = "Match Notes"

_ALL_ROW_COLUMNS = (
    COL_TITLE,
    COL_COMPANY,
    COL_LOCATION,
    COL_SALARY,
    COL_POSTED,
    COL_TYPE,
    COL_INDUSTRY,
    COL_SIZE,
    COL_HQ,
    COL_FOUNDED,
    COL_MARKET_CAP,
    COL_DESCRIPTION,
    COL_STABILITY,
    COL_GROWTH,
    *COL_NEWS,
    *COL_NEWS_URL,
    COL_REC,
    COL_ENRICHED_DATE,
    COL_APPLY,
    COL_STATUS,
    COL_MATCH_SCORE,
    COL_MATCH_NOTES,
)


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in _ALL_ROW_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df


def _s(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).strip()


def _format_year_display(val) -> str:
    """Show founding year without Excel-style trailing .0 (e.g. 1995 not 1995.0)."""
    if val is None:
        return ""
    try:
        if pd.isna(val):
            return ""
    except TypeError:
        pass
    try:
        f = float(val)
        if pd.isna(f):
            return ""
        if f == int(f):
            return str(int(f))
    except (TypeError, ValueError, OverflowError):
        pass
    s = str(val).strip()
    if re.fullmatch(r"\d+\.0+", s):
        return s.split(".")[0]
    try:
        f = float(s.replace(",", ""))
        if f == int(f):
            return str(int(f))
    except ValueError:
        pass
    return s


def badge_stability_class(text: str) -> str:
    """Stability: green Strong, yellow Stable, red Declining, gray Unknown/Uncertain/empty."""
    t = _s(text).lower()
    if not t:
        return "status-next"
    if re.search(r"\bunknown\b", t) or re.search(r"\buncertain\b", t):
        return "status-next"
    if "declin" in t:
        return "status-declining"
    if re.search(r"\bunstable\b", t):
        return "status-next"
    if re.search(r"\bstrong\b", t):
        return "status-done"
    if re.search(r"\bstable\b", t):
        return "status-active"
    return "status-next"


def badge_growth_class(text: str) -> str:
    """Growth trend: green Growing, yellow Stable, red Declining, gray Unknown/Uncertain/empty."""
    t = _s(text).lower()
    if not t:
        return "status-next"
    if re.search(r"\bunknown\b", t) or re.search(r"\buncertain\b", t):
        return "status-next"
    if "declin" in t:
        return "status-declining"
    if "not growing" in t.replace("-", " "):
        return "status-next"
    if re.search(r"\bgrowing\b", t):
        return "status-done"
    if re.search(r"\bstable\b", t):
        return "status-active"
    return "status-next"


def _match_score_value(raw) -> int | None:
    """Return the match score as an int, or None when missing/blank/non-numeric."""
    if raw is None:
        return None
    try:
        if pd.isna(raw):
            return None
    except (TypeError, ValueError):
        pass
    s = str(raw).strip()
    if not s or s.lower() == "nan":
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def badge_match_class(score) -> str:
    """Resume match: green >=70, yellow 50-69, red <50, gray when no score."""
    value = _match_score_value(score)
    if value is None:
        return "status-next"
    if value >= 70:
        return "status-done"
    if value >= 50:
        return "status-active"
    return "status-declining"


def build_tailor_command(company: str, title: str, url: str) -> str:
    return " ".join(
        [
            "python3",
            "resume_tailor.py",
            "--company",
            shlex.quote(company or "Unknown"),
            "--title",
            shlex.quote(title or "Position"),
            "--url",
            shlex.quote(url or ""),
        ]
    )


def _meta_block(label: str, value: str) -> str:
    v = _s(value)
    if not v:
        return ""
    return f"""<div class="meta-pair">
      <div class="stat-label">{html.escape(label)}</div>
      <div class="meta-value">{html.escape(v)}</div>
    </div>"""


def _url_from_text(text: str) -> str:
    m = re.search(r"https?://[^\s<>\"'\]]+", text)
    if not m:
        return ""
    return m.group(0).rstrip(").,;'\"]")


def _http_url_reachable(url: str, cache: dict[str, bool], timeout: float = 8.0) -> bool:
    """True if URL returns a 2xx/3xx success with a short GET (browser-like UA)."""
    if url in cache:
        return cache[url]
    if not url.startswith(("http://", "https://")):
        cache[url] = False
        return False
    try:
        import requests
    except ImportError:
        cache[url] = True
        return True
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        with requests.get(url, allow_redirects=True, timeout=timeout, headers=headers, stream=True) as r:
            if not (200 <= r.status_code < 400):
                cache[url] = False
                return False
            for _ in r.iter_content(8192):
                break
        cache[url] = True
        return True
    except Exception:
        cache[url] = False
        return False


def _news_entries(row: pd.Series) -> list[tuple[str, str]]:
    """Pairs of (news line, article URL) for each non-empty news slot."""
    out = []
    for col, url_col in zip(COL_NEWS, COL_NEWS_URL):
        t = _s(row.get(col, ""))
        if not t:
            continue
        u = _s(row.get(url_col, ""))
        if u and not u.startswith(("http://", "https://")):
            u = ""
        if not u:
            u = _url_from_text(t)
        out.append((t, u))
    return out


def _news_li(
    text: str,
    url: str,
    *,
    verify_urls: bool,
    url_cache: dict[str, bool],
) -> str:
    t_esc = html.escape(text)
    u = _s(url)
    if not u:
        u = _url_from_text(text)
    if not u.startswith(("http://", "https://")):
        return f"<li>{t_esc}</li>"
    u_esc = html.escape(u, quote=True)
    if verify_urls and not _http_url_reachable(u, url_cache):
        u_plain = html.escape(u)
        return f"""<li class="news-item-plain">
      <div class="news-line-text">{t_esc}</div>
      <div class="stat-label news-url-hint">URL — copy into your browser</div>
      <pre class="news-url-copy" tabindex="0">{u_plain}</pre>
    </li>"""
    return f"""<li><a class="news-link" href="{u_esc}" target="_blank" rel="noopener noreferrer">{t_esc}</a></li>"""


def render_job_card(
    row: pd.Series,
    *,
    verify_news_urls: bool,
    url_cache: dict[str, bool],
) -> str:
    title = _s(row.get(COL_TITLE, ""))
    company = _s(row.get(COL_COMPANY, ""))
    apply_url = _s(row.get(COL_APPLY, ""))
    stability = _s(row.get(COL_STABILITY, ""))
    growth = _s(row.get(COL_GROWTH, ""))
    match_score = row.get(COL_MATCH_SCORE, "")
    match_notes = _s(row.get(COL_MATCH_NOTES, ""))

    stab_cls = badge_stability_class(stability)
    grow_cls = badge_growth_class(growth)
    match_value = _match_score_value(match_score)
    match_cls = badge_match_class(match_score)

    meta_primary = "".join(
        [
            _meta_block("Location", row.get(COL_LOCATION, "")),
            _meta_block("Salary", row.get(COL_SALARY, "")),
            _meta_block("Posted", row.get(COL_POSTED, "")),
            _meta_block("Employment type", row.get(COL_TYPE, "")),
        ]
    )
    intel_meta = "".join(
        [
            _meta_block("Industry", row.get(COL_INDUSTRY, "")),
            _meta_block("HQ location", row.get(COL_HQ, "")),
            _meta_block("Company size", row.get(COL_SIZE, "")),
            _meta_block("Founded", _format_year_display(row.get(COL_FOUNDED, ""))),
            _meta_block("Market cap", row.get(COL_MARKET_CAP, "")),
        ]
    )

    desc = _s(row.get(COL_DESCRIPTION, ""))
    desc_html = html.escape(desc) if desc else ""

    news_list = _news_entries(row)
    news_html = ""
    if news_list:
        lis = "".join(
            _news_li(t, u, verify_urls=verify_news_urls, url_cache=url_cache) for t, u in news_list
        )
        news_html = f"""<div class="job-block">
      <div class="stat-label">Recent news</div>
      <ul class="news-list">{lis}</ul>
    </div>"""

    rec = _s(row.get(COL_REC, ""))
    rec_html = ""
    if rec:
        rec_html = f"""<div class="rec-callout">
      <div class="stat-label">Recommendation</div>
      <p class="about-text rec-text">{html.escape(rec)}</p>
    </div>"""

    match_html = ""
    if match_notes:
        segments = [html.escape(seg.strip()) for seg in match_notes.split("|") if seg.strip()]
        note_lines = "".join(f"""<p class="about-text match-text">{seg}</p>""" for seg in segments)
        match_html = f"""<div class="match-callout">
      <div class="stat-label">Resume match notes</div>
      {note_lines}
    </div>"""

    cmd_display = html.escape(build_tailor_command(company, title, apply_url))

    if apply_url:
        view_btn = f"""<a class="btn btn-accent" href="{html.escape(apply_url, quote=True)}" target="_blank" rel="noopener noreferrer">View Job →</a>"""
    else:
        view_btn = """<span class="btn btn-disabled" aria-disabled="true">No apply URL</span>"""

    match_badge = (
        f"""\n      <span class="wave-status {match_cls}">Match: {match_value}%</span>"""
        if match_value is not None else ""
    )
    badges = f"""<div class="badge-row">
      <span class="wave-status {stab_cls}">Stability: {html.escape(stability or "—")}</span>
      <span class="wave-status {grow_cls}">Growth trend: {html.escape(growth or "—")}</span>{match_badge}
    </div>"""

    enriched_raw = row.get(COL_ENRICHED_DATE, "")
    enriched_date_row = ""
    if _s(enriched_raw):
        enriched_date_row = f"""<div class="job-meta-grid job-meta-grid--enriched-date">{_meta_block("Enriched date", enriched_raw)}</div>"""

    return f"""<article class="stat-card job-card">
    <h2 class="project-title">{html.escape(title or "(No title)")}</h2>
    <p class="project-desc company-line">{html.escape(company or "(No company)")}</p>
    <div class="job-meta-grid">{meta_primary}</div>
    <div class="job-intel">
    <div class="job-meta-grid">{intel_meta}</div>
    {badges}
    <div class="job-block">
      <div class="stat-label">Description</div>
      <div class="description-body">{desc_html or "—"}</div>
    </div>
    {news_html}
    {rec_html}
    {match_html}
    {enriched_date_row}
    </div>
    <div class="job-block command-intro">
      <p class="terminal-comment command-note">Copy this command and paste into your terminal to tailor your resume</p>
      <div class="project-sidebar command-sidebar">
        <pre class="terminal command-pre"><span class="terminal-prompt">{cmd_display}</span></pre>
      </div>
    </div>
    <div class="hero-links job-actions">{view_btn}</div>
  </article>"""


def render_empty_body(report_date: str) -> str:
    return f"""<section class="job-report-section job-report-hero">
    <p class="section-tag">Job report</p>
    <h1 class="section-title">Interested Roles</h1>
    <p class="project-desc empty-msg">No listings with Status set to <strong>Interested</strong> were found in the spreadsheet. Mark roles as Interested in <span class="tag">job_listings.xlsx</span> and run this script again.</p>
    <p class="about-text">Report date: {html.escape(report_date)}</p>
  </section>"""


def render_jobs_body(
    rows: pd.DataFrame,
    report_date: str,
    n: int,
    *,
    verify_news_urls: bool,
    url_cache: dict[str, bool],
) -> str:
    cards = "\n".join(
        render_job_card(
            rows.loc[i],
            verify_news_urls=verify_news_urls,
            url_cache=url_cache,
        )
        for i in rows.index
    )
    return f"""<section class="job-report-section job-report-hero">
    <p class="section-tag">Job report</p>
    <h1 class="section-title">Interested Roles</h1>
    <p class="project-desc report-summary">{html.escape(report_date)} · {n} job{"s" if n != 1 else ""}</p>
  </section>
  <section class="job-report-section job-list-section">
    <div class="job-list">
{cards}
    </div>
  </section>"""


def _report_css() -> str:
    return """
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --ink:      #0f0e0c;
      --paper:    #f5f2eb;
      --accent:   #2d5a27;
      --muted:    #6b6760;
      --border:   #d4cfc6;
      --code-bg:  #1a1916;
      --code-fg:  #a8e6a3;
    }

    html { scroll-behavior: smooth; }

    body {
      background: var(--paper);
      color: var(--ink);
      font-family: 'DM Sans', sans-serif;
      font-weight: 300;
      line-height: 1.7;
      overflow-x: hidden;
    }

    section {
      padding: 6rem 5rem;
      border-top: 1px solid var(--border);
    }

    .section-tag {
      font-family: 'DM Mono', monospace;
      font-size: 0.72rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 1rem;
    }

    .section-title {
      font-family: 'DM Serif Display', serif;
      font-size: clamp(2rem, 4vw, 3rem);
      line-height: 1.1;
      margin-bottom: 3rem;
    }

    .project-title {
      font-family: 'DM Serif Display', serif;
      font-size: 1.8rem;
      margin-bottom: 1rem;
    }

    .project-desc {
      color: var(--muted);
      margin-bottom: 2rem;
      font-size: 1rem;
    }

    .about-text {
      font-size: 1.05rem;
      color: var(--muted);
      line-height: 1.8;
    }

    .stat-card {
      border: 1px solid var(--border);
      padding: 1.5rem;
    }

    .stat-label {
      font-family: 'DM Mono', monospace;
      font-size: 0.7rem;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 0.4rem;
    }

    .tag {
      font-family: 'DM Mono', monospace;
      font-size: 0.72rem;
      padding: 0.3rem 0.7rem;
      border: 1px solid var(--border);
      color: var(--muted);
      letter-spacing: 0.04em;
    }

    .hero-links {
      display: flex;
      gap: 1rem;
      flex-wrap: wrap;
    }

    .btn {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.65rem 1.4rem;
      font-family: 'DM Mono', monospace;
      font-size: 0.8rem;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      text-decoration: none;
      border: 1px solid var(--ink);
      color: var(--ink);
      transition: all 0.2s;
    }

    .btn:hover {
      background: var(--ink);
      color: var(--paper);
    }

    .btn-accent {
      background: var(--accent);
      border-color: var(--accent);
      color: white;
    }

    .btn-accent:hover {
      background: #1e3d1a;
      border-color: #1e3d1a;
      color: white;
    }

    .btn-disabled {
      opacity: 0.45;
      cursor: not-allowed;
      pointer-events: none;
    }

    .project-sidebar {
      padding: 3rem;
      background: var(--ink);
      color: var(--paper);
    }

    .terminal {
      font-family: 'DM Mono', monospace;
      font-size: 0.78rem;
      line-height: 1.8;
    }

    .terminal-prompt { color: var(--code-fg); }
    .terminal-comment { color: #666; }

    .wave-status {
      font-family: 'DM Mono', monospace;
      font-size: 0.65rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-top: 1rem;
      padding: 0.25rem 0.6rem;
      display: inline-block;
    }

    .status-done {
      background: #e8f5e9;
      color: #2e7d32;
    }

    .status-active {
      background: #fff3e0;
      color: #e65100;
    }

    .status-next {
      background: var(--border);
      color: var(--muted);
    }

    .status-declining {
      background: #ffebee;
      color: #b71c1c;
    }

    footer {
      padding: 2rem 5rem;
      border-top: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    footer p {
      font-family: 'DM Mono', monospace;
      font-size: 0.72rem;
      color: var(--muted);
      letter-spacing: 0.06em;
    }

    .job-report-main {
      max-width: 1100px;
      margin: 0 auto;
      width: 100%;
    }

    .job-report-main .job-report-hero {
      border-top: none;
      padding-top: 1.5rem;
      padding-bottom: 0.5rem;
    }

    .job-report-main .job-report-hero .section-tag {
      margin-bottom: 0.4rem;
    }

    .job-report-main .job-report-hero .section-title {
      margin-bottom: 0.35rem;
    }

    .job-report-main .job-report-hero .project-desc,
    .job-report-main .job-report-hero .about-text {
      margin-bottom: 0.75rem;
    }

    .job-report-main .report-summary {
      margin-top: 0;
      margin-bottom: 0;
    }

    .job-report-main section.job-list-section {
      padding-top: 1.25rem;
      padding-bottom: 5rem;
    }

    .job-card {
      margin-bottom: 2rem;
      overflow-wrap: anywhere;
      word-wrap: break-word;
    }

    .job-card:last-child { margin-bottom: 0; }

    .company-line { margin-top: -0.5rem; }

    .job-meta-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 1.25rem 2.5rem;
      margin-bottom: 1.5rem;
    }

    .meta-pair { min-width: 8rem; max-width: 100%; }

    .meta-value {
      font-size: 0.95rem;
      font-weight: 400;
      color: var(--ink);
    }

    .badge-row {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      align-items: center;
      margin: 0.5rem 0 1.25rem;
    }

    .badge-row .wave-status { margin-top: 0; }

    .job-block { margin-bottom: 1.5rem; }

    .description-body {
      font-size: 1rem;
      color: var(--ink);
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    .news-list {
      margin: 0.5rem 0 0 1.25rem;
      color: var(--muted);
    }

    .news-list li { margin-bottom: 0.35rem; }

    .news-list a.news-link {
      color: var(--accent);
      text-decoration: underline;
      text-underline-offset: 0.15em;
    }

    .news-list a.news-link:hover {
      color: var(--ink);
    }

    .news-item-plain {
      margin-bottom: 0.75rem;
    }

    .news-line-text {
      color: var(--ink);
      margin-bottom: 0.35rem;
    }

    .news-url-hint {
      margin-top: 0.25rem;
      margin-bottom: 0.2rem;
    }

    .news-url-copy {
      font-family: 'DM Mono', monospace;
      font-size: 0.72rem;
      line-height: 1.5;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      word-break: break-all;
      margin: 0;
      padding: 0.6rem 0.75rem;
      border: 1px solid var(--border);
      background: var(--paper);
      color: var(--ink);
      max-width: 100%;
    }

    .rec-callout {
      border: 1px solid var(--border);
      padding: 1.2rem;
      background: #e8f5e9;
      margin: 1rem 0 1.5rem;
    }

    .rec-text { margin-bottom: 0; color: var(--ink); }

    .match-callout {
      border: 1px solid var(--border);
      border-left: 3px solid var(--border);
      padding: 1.2rem;
      background: var(--paper);
      margin: 1rem 0 1.5rem;
    }

    .match-text { margin: 0 0 0.4rem; color: var(--ink); }
    .match-callout .match-text:last-child { margin-bottom: 0; }

    .command-intro { margin-top: 1rem; }

    .command-note {
      font-family: 'DM Mono', monospace;
      font-size: 0.78rem;
      margin-bottom: 0.75rem;
    }

    .command-sidebar { padding: 1.25rem 1.5rem; }

    .command-pre {
      margin: 0;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    .job-actions { margin-top: 1.5rem; }

    .empty-msg strong { font-weight: 500; color: var(--ink); }

    @media (max-width: 900px) {
      section { padding: 4rem 2rem; }
      .job-report-main .job-report-hero {
        padding: 1.25rem 2rem 0.5rem;
      }
      .job-report-main section.job-list-section {
        padding: 1rem 2rem 3.5rem;
      }
      footer { flex-direction: column; gap: 0.5rem; text-align: center; }
    }
"""


def html_document(title: str, body_inner: str, report_date: str) -> str:
    css = _report_css()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
  <style>
{css}
  </style>
</head>
<body>
  <main class="job-report-main">
{body_inner}
    <footer>
      <p>Job listings report</p>
      <p>{html.escape(report_date)}</p>
    </footer>
  </main>
</body>
</html>
"""


def generate_report(
    excel_path: str | Path,
    output_path: str | Path | None = None,
    *,
    verify_news_urls: bool = True,
) -> Path:
    excel_path = Path(excel_path)
    if output_path is None:
        output_path = Path("output") / f"job_report_{date.today().isoformat()}.html"
    else:
        output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = _ensure_columns(pd.read_excel(excel_path))

    mask = df[COL_STATUS].astype(str).str.strip().str.lower() == "interested"
    interested = df.loc[mask].copy()

    report_date = date.today().isoformat()
    title = f"Job report — {report_date}"

    if interested.empty:
        body = render_empty_body(report_date)
    else:
        url_cache: dict[str, bool] = {}
        body = render_jobs_body(
            interested,
            report_date,
            len(interested),
            verify_news_urls=verify_news_urls,
            url_cache=url_cache,
        )

    doc = html_document(title, body, report_date)
    output_path.write_text(doc, encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build HTML report from job listings (Interested only).")
    parser.add_argument(
        "excel_file",
        nargs="?",
        help="Source Excel file (default: job_listings.xlsx)",
    )
    parser.add_argument(
        "--input",
        dest="input_file",
        default=None,
        help="Source Excel file (legacy option; positional filename also works)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output HTML path (default: job_report_YYYY-MM-DD.html)",
    )
    parser.add_argument(
        "--skip-news-url-check",
        action="store_true",
        help="Skip HTTP checks on news URLs (faster; always emit clickable links, may 403 in browser)",
    )
    args = parser.parse_args()
    input_file = args.excel_file or args.input_file or os.path.join("output", "job_listings.xlsx")
    out = generate_report(
        input_file,
        args.output,
        verify_news_urls=not args.skip_news_url_check,
    )
    print(f"Wrote {out.resolve()}")


if __name__ == "__main__":
    main()
