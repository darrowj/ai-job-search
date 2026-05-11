import requests
import json
from datetime import date
from dotenv import load_dotenv
import os

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

    print(f"Status: {response.status_code}")
    print(f"Jobs found: {len(data.get('data', {}).get('jobs', []))}")

    
    return data

def display_jobs(data):
    jobs = data.get("data", {}).get("jobs", [])
    if not jobs:
        print("No jobs found.")
        return
    for job in jobs:
        print("---")
        print(f"Title:    {job.get('job_title')}")
        print(f"Company:  {job.get('employer_name')}")
        print(f"Location: {job.get('job_location')}")
        print(f"Salary:   {job.get('job_salary_string', 'Not listed')}")
        print(f"Posted:   {job.get('job_posted_at', 'Unknown')}")
        print(f"URL:      {job.get('job_apply_link')}")

# Run it
results = search_jobs("IT Delivery Manager", "Boston MA")
display_jobs(results)