import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

# Load .env file (so GEMINI_API_KEY is available)
load_dotenv()

# Configure Gemini with API key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def generate_resume(personal_info, education, experience, skills, target_role, job_description, tone):
    prompt = f"""
You are an expert resume writer and ATS specialist.

User profile:
Personal info: {personal_info}
Education: {education}
Experience: {experience}
Skills: {skills}
Target role: {target_role}

Job description:
{job_description}

Requirements:
- Optimize for ATS with relevant keywords from the job description.
- Rewrite experience as strong bullet points with action verbs and quantification where possible.
- Maintain a {tone} tone (examples: corporate, creative, entry level, technical).
- Return a JSON object with this structure:

{{
  "summary": "...",
  "skills": ["..."],
  "experience": [
    {{
      "company": "...",
      "title": "...",
      "location": "...",
      "start_date": "...",
      "end_date": "...",
      "bullets": ["...", "..."]
    }}
  ],
  "education": [
    {{
      "institution": "...",
      "degree": "...",
      "year": "..."
    }}
  ],
  "projects": [
    {{
      "name": "...",
      "description": "...",
      "tech_stack": ["..."]
    }}
  ]
}}

Only output valid JSON.
"""

    model = genai.GenerativeModel("models/gemini-2.0-flash")

    response = model.generate_content(prompt)

    # Gemini puts text response here:
    text = response.text

    return json.loads(text)
