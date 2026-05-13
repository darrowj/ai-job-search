import requests
import json
from datetime import date
from dotenv import load_dotenv
import os
import pandas as pd
import argparse

# Load API key from .env file
load_dotenv()
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

def search_jobs(search_term, location, num_pages=1):
    print(f"Searching for '{search_term}' jobs in '{location}'...")

    url = "https://jsearch.p.rapidapi.com/search-v2"

    querystring = {
        "query": f"{search_term} in {location}",
        "num_pages": str(num_pages),
        "country": "us",
        "date_posted": "all"
    }

    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": "jsearch.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY
    }

    response = requests.get(url, headers=headers, params=querystring)
    data = response.json()

    jobs = data.get("data", {}).get("jobs", [])
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