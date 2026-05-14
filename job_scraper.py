import requests
from datetime import date
from dotenv import load_dotenv
import os
import pandas as pd
import argparse

# Load API credentials from .env file
load_dotenv()
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")

ADZUNA_RESULTS_PER_PAGE = 50  # Adzuna allows up to 50 per page


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


def search_jobs(search_term, location, num_pages=1):
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search for jobs and save to Excel")
    parser.add_argument(
        "--titles",
        nargs="+",
        default=["IT Delivery Manager"],
        help='Job titles to search. Example: --titles "IT Delivery Manager" "Program Manager"'
    )
    parser.add_argument(
        "--locations",
        nargs="+",
        default=["Boston MA"],
        help='Locations to search. Example: --locations "Boston MA" "Worcester MA"'
    )
    parser.add_argument(
        "--output",
        default="job_listings.xlsx",
        help="Output Excel filename"
    )
    args = parser.parse_args()

    # Run all combinations of titles and locations
    all_rows = []
    for title in args.titles:
        for location in args.locations:
            jobs = search_jobs(title, location)
            rows = jobs_to_rows(jobs, title, location)
            all_rows.extend(rows)

    print(f"\nTotal listings before dedup: {len(all_rows)}")
    save_to_excel(all_rows, args.output)