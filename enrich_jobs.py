import os
import requests
import pandas as pd
from dotenv import load_dotenv
import anthropic
import json
from datetime import date
from openpyxl import load_workbook
from openpyxl.styles import Alignment

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
client = anthropic.Anthropic()

# ── Data fetchers ──────────────────────────────────────────────────────────

def get_wikipedia_summary(company_name):
    """Pull company overview from Wikipedia."""
    try:
        url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + company_name.replace(" ", "_")
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("extract", "")
        return ""
    except:
        return ""

def get_news(company_name, num_articles=3):
    """Pull recent news headlines from NewsAPI."""
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": f'"{company_name}"',
            "sortBy": "publishedAt",
            "pageSize": num_articles,
            "language": "en",
            "apiKey": NEWS_API_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        print(f"  News API status: {response.status_code}")

        if response.status_code == 200:
            articles = response.json().get("articles", [])
            print(f"  Articles returned: {len(articles)}")
            headlines = []
            for a in articles:
                title = a.get("title", "")
                published = a.get("publishedAt", "")[:10]
                source = a.get("source", {}).get("name", "")
                headlines.append(f"{published} [{source}]: {title}")
            return headlines
        else:
            print(f"  News API error: {response.json().get('message', 'Unknown error')}")
        return []
    except Exception as e:
        print(f"  News fetch error: {e}")
        return []

def get_company_intel(company_name, job_title):
    """Use Claude to synthesize all available data into a structured brief."""
    wiki = get_wikipedia_summary(company_name)
    news = get_news(company_name)

    news_text = "\n".join(news) if news else "No recent news found."

    print(f"  Wikipedia data: {'Found' if wiki else 'Not found'}")
    print(f"  News headlines: {len(news)} found")

    prompt = f"""
You are a business intelligence analyst. Based on the information below,
provide a structured company brief for a job seeker considering applying
to this company.

COMPANY: {company_name}
JOB TITLE THEY ARE CONSIDERING: {job_title}

WIKIPEDIA SUMMARY:
{wiki if wiki else "No Wikipedia data found — use general knowledge."}

RECENT NEWS HEADLINES:
{news_text}

Return ONLY a JSON object in this exact format — no other text:
{{
  "industry": "primary industry",
  "hq_location": "city, state/country",
  "company_size": "estimated employee count or range",
  "founded": "year founded if known",
  "market_cap": "market cap or revenue estimate if known, or Private",
  "description": "2-3 sentence plain english summary of what the company does",
  "stability": "Strong / Stable / Uncertain / Unknown",
  "growth_trend": "Growing / Stable / Declining / Unknown",
  "news_1": "most recent relevant headline with date, or No recent news found",
  "news_2": "second most recent headline with date, or empty string",
  "news_3": "third most recent headline with date, or empty string",
  "recommendation": "1-2 sentence assessment of this company as an employer given the job seeker's target role"
}}
"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text
    start = response_text.find("{")
    end = response_text.rfind("}") + 1
    return json.loads(response_text[start:end])

# ── Text wrap columns in Excel ─────────────────────────────────────────────

def apply_formatting(excel_file):
    """Apply text wrapping to description and recommendation columns."""
    wb = load_workbook(excel_file)
    ws = wb.active

    # Find columns to wrap
    wrap_columns = ["Description", "Recommendation", "News 1", "News 2", "News 3"]
    col_indices = {}

    for cell in ws[1]:  # Header row
        if cell.value in wrap_columns:
            col_indices[cell.column] = cell.value

    # Apply wrap to those columns
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            if cell.column in col_indices:
                cell.alignment = Alignment(wrap_text=True, vertical="top")

    # Set column widths
    col_widths = {
        "Description":    50,
        "Recommendation": 50,
        "News 1":         60,
        "News 2":         60,
        "News 3":         60,
    }

    for cell in ws[1]:
        if cell.value in col_widths:
            ws.column_dimensions[cell.column_letter].width = col_widths[cell.value]

    # Set row height for data rows
    for row_num in range(2, ws.max_row + 1):
        ws.row_dimensions[row_num].height = 80

    wb.save(excel_file)
    print("Formatting applied.")

# ── Main enrichment loop ───────────────────────────────────────────────────

def enrich_jobs(excel_file="job_listings.xlsx"):
    print(f"Loading {excel_file}...")
    df = pd.read_excel(excel_file)

    # Find rows marked as Interested
    interested = df[df["Status"].str.strip().str.lower() == "interested"]

    if interested.empty:
        print("No jobs marked as 'Interested' found.")
        print("Open job_listings.xlsx, change Status to 'Interested' for jobs you want,  then run again.")
        return

    print(f"Found {len(interested)} jobs marked as Interested. Enriching...")

    # Add new columns if they don't exist
    new_cols = ["Industry", "HQ Location", "Company Size", "Founded",
                "Market Cap", "Description", "Stability", "Growth Trend",
                "News 1", "News 2", "News 3", "Recommendation", "Enriched Date"]
    for col in new_cols:
        if col not in df.columns:
            df[col] = ""

    # Enrich each interested row
    for idx, row in interested.iterrows():
        company = row["Company"]
        title = row["Title"]
        print(f"\nResearching: {company}...")

        try:
            intel = get_company_intel(company, title)

            df.at[idx, "Industry"]       = intel.get("industry", "")
            df.at[idx, "HQ Location"]    = intel.get("hq_location", "")
            df.at[idx, "Company Size"]   = intel.get("company_size", "")
            df.at[idx, "Founded"]        = intel.get("founded", "")
            df.at[idx, "Market Cap"]     = intel.get("market_cap", "")
            df.at[idx, "Description"]    = intel.get("description", "")
            df.at[idx, "Stability"]      = intel.get("stability", "")
            df.at[idx, "Growth Trend"]   = intel.get("growth_trend", "")
            df.at[idx, "News 1"]         = intel.get("news_1", "")
            df.at[idx, "News 2"]         = intel.get("news_2", "")
            df.at[idx, "News 3"]         = intel.get("news_3", "")
            df.at[idx, "Recommendation"] = intel.get("recommendation", "")
            df.at[idx, "Enriched Date"]  = str(date.today())

            print(f"  ✓ Done — {intel.get('stability')} / {intel.get('growth_trend')}")

        except Exception as e:
            print(f"  ✗ Error enriching {company}: {e}")

    # Save to Excel
    df.to_excel(excel_file, index=False)
    print(f"\nData saved to {excel_file}")

    # Apply formatting
    apply_formatting(excel_file)
    print(f"Enrichment complete. Open {excel_file} to review.")

# ── Run ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    enrich_jobs()