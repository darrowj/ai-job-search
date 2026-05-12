import anthropic
import json
from dotenv import load_dotenv

# Load API keys from .env
load_dotenv()

# Load your master resume
with open("master_resume.json", "r") as f:
    master_resume = json.load(f)

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
        max_tokens=1024,
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

# Job details
job_title = "Manager, IT Delivery Team"
job_description = """
This position is responsible for leading the successful delivery of 
Strategic programs across Technology and Innovation. This position will 
lead the remediation efforts of various projects focused on delivering 
execution in a matrixed environment. The person in this role engages with 
all levels of staff and management in the technology and business units. 
This role operates in a fast-paced environment with teams of motivated 
colleagues to deliver high quality solutions that add value to colleague 
and client experiences. Successful incumbent will be capable of working 
in a rapidly changing industry/environment, can tolerate ambiguity, 
demonstrate problem-solving leadership and act as a change agent at both 
the organizational level and via solutions delivery.

Required: 10 years IT experience, 10 years Program/Project Management, 
7 years Financial Services, 5 years process improvement, 6 years 
supervisory experience. PMP or CSM preferred. Agile, waterfall, iterative 
delivery experience. Vendor management. Stakeholder management.
"""

# Run the tailoring
result = tailor_resume(job_title, job_description)

# Save output for resume generator
with open("tailored_output.json", "w") as f:
    json.dump(result, f, indent=2)

print("Tailoring complete. Match score:", result["match_score"])
print("Saved to tailored_output.json")