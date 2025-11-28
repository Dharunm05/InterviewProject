import json
import re
import google.generativeai as genai

# ⚠️ DO NOT configure API key here.
# It is configured in temp.py using genai.configure(api_key="...")

def extract_json(text: str):
    """
    Extracts the first JSON object from the model response text.
    Cleans ```json ... ``` wrappers if present.
    """
    # Find JSON block between first '{' and last '}'
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        print("\n❌ ERROR: No JSON detected in model response.\n")
        print("🔍 Raw text:\n", text)
        raise ValueError("Model did not return JSON.")

    cleaned = match.group(0)

    # Remove markdown fences if they exist
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    # Debug
    print("\n🧹 CLEANED JSON STRING:\n", cleaned, "\n")

    return json.loads(cleaned)


def generate_resume(personal_info, education, experience, skills, target_role, job_description, tone):
    """
    Ask Gemini to generate a structured resume as JSON.
    """
    prompt = f"""
You are an expert resume writer and ATS specialist.

Return ONLY a JSON object (no extra text, no markdown, no explanations).

Required JSON format:
{{
  "summary": "...",
  "skills": ["..."],
  "experience": [
    {{
      "company": "...",
      "title": "...",
      "bullets": ["...", "..."]
    }}
  ],
  "education": [
    {{
      "institution": "...",
      "degree": "...",
      "year": "..."
    }}
  ]
}}

User Profile:
Personal Info: {personal_info}
Education: {education}
Experience: {experience}
Skills: {skills}
Target Role: {target_role}
Job Description: {job_description}
Tone: {tone}
"""

    model = genai.GenerativeModel("models/gemini-2.0-flash")

    response = model.generate_content(prompt)

    # Try to get the text safely
    text = (response.text or "").strip()

    print("\n🧠 RAW MODEL OUTPUT:\n", text, "\n")

    # 🔴 DO NOT DO: return json.loads(text)
    # ✅ Instead:
    return extract_json(text)
