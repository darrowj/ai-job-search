import requests
from datetime import date, datetime, timedelta, timezone
from dotenv import load_dotenv
import os
import pandas as pd
import argparse
import json
import re

# Load API credentials from .env file
load_dotenv()
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")
MIN_SALARY = int(os.getenv("MIN_SALARY", 0))

ADZUNA_RESULTS_PER_PAGE = 50  # Adzuna allows up to 50 per page
DEFAULT_CONFIG_FILE = "search_config.json"


def _format_adzuna_salary(job):
    smin = job.get("salary_min")
    smax = job.get("salary_max")
    if smin is None and smax is None:
        return "Not listed"

    def fmt(n):
        return f"${n:,.0f}"

    suffix = " (estimate)" if job.get("salary_is_predicted") else ""

    if smin is not None and smax is not None:
        if smin == smax:
            return f"{fmt(smin)}{suffix}"
        low, high = (smin, smax) if smin <= smax else (smax, smin)
        return f"{fmt(low)} - {fmt(high)}{suffix}"
    if smin is not None:
        return f"{fmt(smin)}+{suffix}"
    return f"Up to {fmt(smax)}{suffix}"


def _adzuna_job_to_row_shape(job):
    """Map Adzuna search results to the same keys jobs_to_rows expects."""
    company = job.get("company") or {}
    loc = job.get("location") or {}
    parts = [p for p in (job.get("contract_time"), job.get("contract_type")) if p]
    employment = " / ".join(parts) if parts else "Unknown"
    blob = f"{job.get('title') or ''} {(job.get('description') or '')[:800]}".lower()
    is_remote = any(
        w in blob for w in ("remote", "work from home", "wfh", "fully remote", "100% remote")
    )
    return {
        "job_title": job.get("title"),
        "employer_name": company.get("display_name", ""),
        "job_location": loc.get("display_name", ""),
        "job_salary_string": _format_adzuna_salary(job),
        "job_posted_at": job.get("created") or "Unknown",
        "job_employment_type": employment,
        "job_is_remote": is_remote,
        "job_publisher": "Adzuna",
        "job_apply_link": job.get("redirect_url") or "",
    }


def load_search_config(filename=DEFAULT_CONFIG_FILE):
    config_path = os.path.join(os.path.dirname(__file__), filename)
    with open(config_path, "r") as f:
        raw_config = json.load(f)
    return {k: v for k, v in raw_config.items() if not k.startswith("_")}


def _parse_adzuna_datetime(value):
    if not value or value == "Unknown":
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_older_than_max_days(job, max_days_old):
    if max_days_old is None:
        return False

    posted_at = _parse_adzuna_datetime(job.get("job_posted_at"))
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


def filter_jobs(jobs, max_days_old=None, require_title_keywords=None):
    counts = {
        "max_days_old": 0,
        "require_title_keywords": 0,
    }
    kept = []

    for job in jobs:
        if _is_older_than_max_days(job, max_days_old):
            counts["max_days_old"] += 1
            continue
        if not _title_matches_required_keyword(job, require_title_keywords):
            counts["require_title_keywords"] += 1
            continue
        kept.append(job)

    return kept, counts


def search_jobs(search_term, location, num_pages=1, min_salary=None, job_type=None):
    print(f"Searching for '{search_term}' jobs in '{location}'...")

    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        print("  Missing ADZUNA_APP_ID or ADZUNA_APP_KEY in environment (.env).")
        return []

    headers = {"Accept": "application/json"}
    all_raw = []

    for page in range(1, num_pages + 1):
        url = f"https://api.adzuna.com/v1/api/jobs/us/search/{page}"
        params = {
            "app_id": ADZUNA_APP_ID,
            "app_key": ADZUNA_APP_KEY,
            "what": search_term,
            "where": location,
            "results_per_page": ADZUNA_RESULTS_PER_PAGE,
            "sort_by": "date",
        }
        if min_salary:
            params["salary_min"] = min_salary
        if job_type == "full_time":
            params["full_time"] = 1

        response = requests.get(url, headers=headers, params=params, timeout=60)
        if response.status_code != 200:
            print(f"  Adzuna API error {response.status_code}: {response.text[:200]}")
            break
        payload = response.json()
        batch = payload.get("results") or []
        all_raw.extend(batch)
        if len(batch) < ADZUNA_RESULTS_PER_PAGE:
            break

    jobs = [_adzuna_job_to_row_shape(j) for j in all_raw]
    print(f"  Found {len(jobs)} jobs.")
    return jobs

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
            "Date Found":  str(date.today()),
            "Status":      "New",
            "Notes":       ""
        })
    return rows

def save_to_excel(all_rows, filename="job_listings.xlsx"):
    if not all_rows:
        print("No jobs to save.")
        return

    df = pd.DataFrame(all_rows)

    # Remove duplicate listings by URL
    before = len(df)
    df = df.drop_duplicates(subset=["Apply URL"])
    after = len(df)
    if before != after:
        print(f"Removed {before - after} duplicate listings.")

    # Sort by company name
    df = df.sort_values("Company")

    df.to_excel(filename, index=False)
    print(f"\nSaved {len(df)} jobs to {filename}")


def _default_output_filename():
    return f"job_listings_{date.today().isoformat()}.xlsx"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search for jobs and save to Excel")
    parser.add_argument(
        "--output",
        default=_default_output_filename(),
        help="Output Excel filename"
    )
    args = parser.parse_args()
    config = load_search_config()

    titles = config.get("titles", [])
    locations = config.get("locations", [])
    pages = int(config.get("pages", 1))
    max_days_old = config.get("max_days_old")
    job_type = config.get("job_type")
    require_title_keywords = config.get("require_title_keywords", [])

    # Run all combinations of titles and locations
    all_rows = []
    total_before_filters = 0
    total_removed_by_date = 0
    total_removed_by_title_allowlist = 0

    for title in titles:
        for location in locations:
            jobs = search_jobs(
                title,
                location,
                num_pages=pages,
                min_salary=MIN_SALARY,
                job_type=job_type,
            )
            total_before_filters += len(jobs)
            jobs, filter_counts = filter_jobs(
                jobs,
                max_days_old=max_days_old,
                require_title_keywords=require_title_keywords,
            )
            total_removed_by_date += filter_counts["max_days_old"]
            total_removed_by_title_allowlist += filter_counts["require_title_keywords"]
            rows = jobs_to_rows(jobs, title, location)
            all_rows.extend(rows)

    print(
        "\nFiltering summary: "
        f"removed {total_removed_by_date} older than {max_days_old} days; "
        f"removed {total_removed_by_title_allowlist} by title allowlist; "
        f"kept {len(all_rows)} of {total_before_filters} jobs before dedup."
    )
    print(f"\nTotal listings before dedup: {len(all_rows)}")
    save_to_excel(all_rows, args.output)