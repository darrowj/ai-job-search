import anthropic
import json
import argparse
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load API keys from .env
load_dotenv()

# Load your master resume
with open("master_resume.json", "r") as f:
    master_resume = json.load(f)

# ── Fetch job description from URL ─────────────────────────────────────────

def fetch_job_description(url):
    print(f"Fetching job description from: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove noise
        for tag in soup(["nav", "header", "footer", "script", "style", "aside"]):
            tag.decompose()

        # Get clean text
        text = soup.get_text(separator=" ", strip=True)

        # Trim to reasonable size for the API
        text = text[:4000]

        print(f"Fetched {len(text)} characters of job description.")
        return text

    except Exception as e:
        print(f"Error fetching URL: {e}")
        return None

# ── Tailor resume using Claude API ────────────────────────────────────────

def tailor_resume(job_title, job_description):
    print(f"Tailoring resume for: {job_title}...")

    client = anthropic.Anthropic()

    prompt = f"""
You are an expert resume writer. I will give you a master resume in JSON 
format and a job description. Your job is to:

1. Read the job description carefully and identify the top 5-6 required 
   skills and experiences
2. Select the most relevant bullets from the master resume that match
3. Lightly adjust the wording of bullets to mirror the job description 
   language — but never invent experience or change facts
4. Return a tailored resume summary and the selected bullets in JSON format

MASTER RESUME:
{json.dumps(master_resume, indent=2)}

JOB TITLE: {job_title}

JOB DESCRIPTION:
{job_description}

Return your response in this exact JSON format:
{{
  "tailored_summary": "the best fitting summary reworded for this role",
  "selected_bullets": [
    {{
      "company": "company name",
      "title": "job title",
      "bullet": "the tailored bullet text"
    }}
  ],
  "key_skills": ["skill1", "skill2", "skill3"],
  "match_score": 85
}}
"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    response_text = message.content[0].text

    # Parse the JSON response
    start = response_text.find("{")
    end = response_text.rfind("}") + 1
    json_str = response_text[start:end]
    result = json.loads(json_str)

    return result

# ── Main ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tailor resume to a job description")
    parser.add_argument("--title",       help="Job title (optional if using --url)")
    parser.add_argument("--company",     required=True, help="Company name")
    parser.add_argument("--description", help="Job description text")
    parser.add_argument("--url",         help="URL of the job posting page")
    args = parser.parse_args()

    # Get description from URL or direct input
    if args.url:
        description = fetch_job_description(args.url)
        if not description:
            print("Failed to fetch job description. Try --description instead.")
            exit(1)
        title = args.title or "Position"
    elif args.description:
        description = args.description
        title = args.title or "Position"
    else:
        print("Error: provide either --url or --description")
        exit(1)

    # Run the tailoring
    result = tailor_resume(title, description)

    # Save output named by company
    output_file = f"tailored_{args.company.replace(' ', '_')}.json"
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nTailoring complete.")
    print(f"Match score:  {result['match_score']} / 100")
    print(f"Key skills:   {', '.join(result['key_skills'])}")
    print(f"Saved to:     {output_file}")