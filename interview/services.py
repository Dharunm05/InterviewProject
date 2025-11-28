import os
import json
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def generate_questions(role, experience, job_description, interview_type, num_questions=5):
    
    prompt = f"""
Generate {num_questions} interview questions for:

Role: {role}
Experience: {experience}
Interview Type: {interview_type}
Job Description: {job_description}

Return ONLY JSON array:
[
  {{"id":"q1","question":"..." }}
]
"""

    model = genai.GenerativeModel("models/gemini-2.0-flash")

    response = model.generate_content(prompt)

    return json.loads(response.text)


def evaluate_answer(question, user_answer, role, job_description):
    
    prompt = f"""
Evaluate the following answer:

Question: {question}
User Answer: {user_answer}
Role: {role}
Job Description: {job_description}

Return JSON in this exact format:
{{
  "scores": {{
    "content_quality": number,
    "behavioral_fit": number,
    "technical_accuracy": number,
    "communication": number
  }},
  "overall_score": number,
  "feedback": ["point1","point2"],
  "improved_answer": "..."
}}
"""

    model = genai.GenerativeModel("models/gemini-2.0-flash")
    response = model.generate_content(prompt)

    return json.loads(response.text)
