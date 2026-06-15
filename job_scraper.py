import requests
from datetime import date, datetime, timedelta, timezone
from dotenv import load_dotenv
import os
import sys
import shutil
import pandas as pd
import argparse
import json
import re

# Load API credentials from .env file
load_dotenv()
JSEARCH_API_KEY = os.getenv("JSEARCH_API_KEY")
MIN_SALARY = int(os.getenv("MIN_SALARY", 0))

JSEARCH_ENDPOINT = "https://api.openwebninja.com/jsearch/search-v2"
REQUEST_TIMEOUT = 30  # seconds
DEFAULT_CONFIG_FILE = "search_config.json"


def _to_number(value):
    """Coerce a salary value to float; return None if missing or non-numeric."""
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except (ValueError, TypeError):
        return None


def _format_salary(smin, smax, period=None):
    """Render a salary range in the same '$X - $Y' style used previously.

    Appends '/hr' when the salary period is hourly. Returns 'Not listed' when
    both bounds are missing.
    """
    if smin is None and smax is None:
        return "Not listed"

    def fmt(n):
        return f"${n:,.0f}"

    suffix = "/hr" if str(period or "").upper() == "HOUR" else ""

    if smin is not None and smax is not None:
        if smin == smax:
            return f"{fmt(smin)}{suffix}"
        low, high = (smin, smax) if smin <= smax else (smax, smin)
        return f"{fmt(low)} - {fmt(high)}{suffix}"
    if smin is not None:
        return f"{fmt(smin)}+{suffix}"
    return f"Up to {fmt(smax)}{suffix}"


def _jsearch_job_to_row_shape(job):
    """Map a JSearch result to the internal keys jobs_to_rows/filter_jobs expect."""
    smin = _to_number(job.get("job_min_salary"))
    smax = _to_number(job.get("job_max_salary"))
    period = job.get("job_salary_period")
    # search-v2 leaves work_arrangement null and populates the boolean
    # job_is_remote instead, so prefer work_arrangement when present and fall
    # back to the boolean flag. Either way this is a structured field, not a
    # regex over the description.
    is_remote = (job.get("work_arrangement") == "remote") or bool(job.get("job_is_remote"))
    return {
        "job_title": job.get("job_title"),
        "employer_name": job.get("employer_name") or "",
        "job_location": job.get("job_location") or "",
        "job_min_salary": smin,
        "job_max_salary": smax,
        "job_salary_string": _format_salary(smin, smax, period),
        "job_posted_at": job.get("job_posted_at_datetime_utc") or "Unknown",
        "job_employment_type": job.get("job_employment_type") or "Unknown",
        "job_is_remote": is_remote,
        "job_publisher": job.get("job_publisher") or "",
        "job_apply_link": job.get("job_apply_link") or "",
        "job_description": (job.get("job_description") or "")[:8000],
    }


def load_search_config(filename=DEFAULT_CONFIG_FILE):
    config_path = os.path.join(os.path.dirname(__file__), filename)
    with open(config_path, "r") as f:
        raw_config = json.load(f)
    return {k: v for k, v in raw_config.items() if not k.startswith("_")}


def _map_date_posted(max_days_old):
    """Map the config's max_days_old to JSearch's date_posted buckets."""
    if max_days_old is None:
        return None
    try:
        d = int(max_days_old)
    except (ValueError, TypeError):
        return None
    if d <= 3:
        return "3days"
    if d <= 7:
        return "week"
    if d <= 30:
        return "month"
    return None


def _parse_datetime(value):
    if not value or value == "Unknown":
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_older_than_max_days(job, max_days_old):
    if max_days_old is None:
        return False

    posted_at = _parse_datetime(job.get("job_posted_at"))
    if posted_at is None:
        return False

    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)

    cutoff = datetime.now(timezone.utc) - timedelta(days=int(max_days_old))
    return posted_at < cutoff


def _title_matches_required_keyword(job, require_title_keywords):
    title = (job.get("job_title") or "").lower()
    required = require_title_keywords or []
    if not required:
        return True

    for keyword in required:
        kw = str(keyword).strip().lower()
        if not kw:
            continue
        if kw.replace(" ", "").isalnum():
            if re_search_word(kw, title):
                return True
        elif kw in title:
            return True
    return False


def re_search_word(keyword, text):
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


def _passes_salary_filter(job, min_salary):
    """Keep listings with no salary data; otherwise require the upper bound
    (or the lower bound when the upper is missing) to clear MIN_SALARY."""
    if not min_salary:
        return True
    smin = job.get("job_min_salary")
    smax = job.get("job_max_salary")
    if smin is None and smax is None:
        return True
    if smax is not None:
        return smax >= min_salary
    return smin >= min_salary


def filter_jobs(jobs, max_days_old=None, require_title_keywords=None,
                min_salary=None, job_type=None):
    counts = {
        "max_days_old": 0,
        "require_title_keywords": 0,
        "min_salary": 0,
    }
    kept = []

    for job in jobs:
        if _is_older_than_max_days(job, max_days_old):
            counts["max_days_old"] += 1
            continue
        if not _title_matches_required_keyword(job, require_title_keywords):
            counts["require_title_keywords"] += 1
            continue
        if not _passes_salary_filter(job, min_salary):
            counts["min_salary"] += 1
            continue
        if job_type == "full_time":
            employment = (job.get("job_employment_type") or "").lower()
            if "full" not in employment:
                continue
        kept.append(job)

    return kept, counts


def search_jobs(query, date_posted=None, max_pages=1):
    """Fetch up to max_pages of JSearch results (10 per page) via cursor paging."""
    print(f"Searching JSearch for '{query}'...", flush=True)

    headers = {"x-api-key": JSEARCH_API_KEY}
    results = []
    cursor = None

    for _ in range(max(1, int(max_pages))):
        params = {"query": query}
        if date_posted:
            params["date_posted"] = date_posted
        if cursor:
            params["cursor"] = cursor

        try:
            response = requests.get(
                JSEARCH_ENDPOINT, headers=headers, params=params, timeout=REQUEST_TIMEOUT
            )
        except requests.RequestException as e:
            print(f"  Request error: {e}", flush=True)
            break

        if response.status_code != 200:
            print(
                f"  JSearch API error {response.status_code}: {response.text[:200]}",
                flush=True,
            )
            break

        payload = response.json()
        # search-v2 nests results under data.jobs and the paging token under
        # data.cursor (not a top-level data[]/next_cursor as some docs state).
        data = payload.get("data") or {}
        batch = data.get("jobs") or []
        results.extend(_jsearch_job_to_row_shape(j) for j in batch)

        cursor = data.get("cursor")
        if not cursor:
            break

    print(f"  Found {len(results)} jobs.", flush=True)
    return results


def jobs_to_rows(jobs, search_term, location):
    rows = []
    for job in jobs:
        rows.append({
            "Search Term": search_term,
            "Search Location": location,
            "Title":       job.get("job_title"),
            "Company":     job.get("employer_name"),
            "Location":    job.get("job_location"),
            "Salary":      job.get("job_salary_string", "Not listed"),
            "Posted":      job.get("job_posted_at", "Unknown"),
            "Type":        job.get("job_employment_type", "Unknown"),
            "Remote":      "Yes" if job.get("job_is_remote") else "No",
            "Publisher":   job.get("job_publisher"),
            "Apply URL":   job.get("job_apply_link"),
            "Job Description": job.get("job_description", ""),
            "Date Found":  str(date.today()),
            "Status":      "New",
            "Notes":       ""
        })
    return rows


def deduplicate_rows(rows):
    """Dedupe on (Company, Title), case-insensitive after stripping. Keep first."""
    seen = set()
    deduped = []
    for r in rows:
        key = (
            str(r.get("Company") or "").strip().lower(),
            str(r.get("Title") or "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped


def save_to_excel(all_rows, filename="job_listings.xlsx"):
    if not all_rows:
        print("No jobs to save.", flush=True)
        return

    os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
    df = pd.DataFrame(all_rows)

    # Sort by company name
    df = df.sort_values("Company")

    df.to_excel(filename, index=False)
    print(f"\nSaved {len(df)} jobs to {filename}", flush=True)


def _default_output_filename():
    return os.path.join("output", "job_listings.xlsx")


def _archive_copy(canonical_path: str) -> str:
    """Keep a dated snapshot under output/archive/ for scrape history."""
    archive_dir = os.path.join("output", "archive")
    os.makedirs(archive_dir, exist_ok=True)
    archive_path = os.path.join(
        archive_dir, f"job_listings_{date.today().isoformat()}.xlsx"
    )
    shutil.copyfile(canonical_path, archive_path)
    print(f"Archived copy: {archive_path}", flush=True)
    return archive_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search for jobs and save to Excel")
    parser.add_argument(
        "--output",
        default=_default_output_filename(),
        help="Output Excel filename"
    )
    args = parser.parse_args()

    if not JSEARCH_API_KEY:
        print(
            "Error: JSEARCH_API_KEY is missing from the environment (.env). Cannot continue.",
            flush=True,
        )
        sys.exit(1)

    config = load_search_config()

    titles = config.get("titles", [])
    locations = config.get("locations", [])
    pages = int(config.get("pages", 1))
    max_days_old = config.get("max_days_old")
    job_type = config.get("job_type")
    require_title_keywords = config.get("require_title_keywords", [])

    date_posted = _map_date_posted(max_days_old)

    # Run all combinations of titles and locations
    all_rows = []
    total_before_filters = 0
    total_removed_by_date = 0
    total_removed_by_title_allowlist = 0
    total_removed_by_salary = 0

    for title in titles:
        for location in locations:
            query = f"{title} in {location}"
            jobs = search_jobs(query, date_posted=date_posted, max_pages=pages)
            total_before_filters += len(jobs)
            jobs, filter_counts = filter_jobs(
                jobs,
                max_days_old=max_days_old,
                require_title_keywords=require_title_keywords,
                min_salary=MIN_SALARY,
                job_type=job_type,
            )
            total_removed_by_date += filter_counts["max_days_old"]
            total_removed_by_title_allowlist += filter_counts["require_title_keywords"]
            total_removed_by_salary += filter_counts["min_salary"]
            rows = jobs_to_rows(jobs, title, location)
            all_rows.extend(rows)

    print(
        "\nFiltering summary: "
        f"removed {total_removed_by_date} older than {max_days_old} days; "
        f"removed {total_removed_by_title_allowlist} by title allowlist; "
        f"removed {total_removed_by_salary} below salary floor; "
        f"kept {len(all_rows)} of {total_before_filters} jobs before dedup.",
        flush=True,
    )

    final_rows = deduplicate_rows(all_rows)
    print(
        f"\nTotal listings before dedup: {len(all_rows)}; after dedup: {len(final_rows)}",
        flush=True,
    )

    save_to_excel(final_rows, args.output)
    default_out = _default_output_filename()
    if final_rows and os.path.normpath(args.output) == os.path.normpath(default_out):
        _archive_copy(args.output)
