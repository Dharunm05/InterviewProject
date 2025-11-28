import os
import json
from io import BytesIO
from flask_cors import CORS


from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_file,
    jsonify,
)
import google.generativeai as genai

# ------------------ GEMINI CONFIG ------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY environment variable is required.")
genai.configure(api_key=GEMINI_API_KEY)

# ------------------ FLASK APP CONFIG ------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "interview", "templates")
STATIC_DIR = os.path.join(BASE_DIR, "interview", "static")

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.config["SECRET_KEY"] = "super-secret-key-change-this"  # needed for session


# Allow API access from React dev server (http://localhost:5173, etc.)
CORS(app, resources={r"/api/*": {"origins": "*"}})


# ------------------ SHARED GEMINI HELPER ------------------
def _get_model():
    """Return a Gemini model instance."""
    return genai.GenerativeModel("models/gemini-2.0-flash")


# ==========================================================
#                       RESUME BUILDER
# ==========================================================

def extract_profile_from_sources(
    basic_fields: dict,
    old_resume_text: str = "",
    linkedin_profile: str = "",
) -> dict:
    """
    Step 2: Data Extraction & Parsing
    """
    prompt = f"""
You are an AI assistant that extracts structured resume data.

Combine the following into one clean, complete profile:
1) Structured form fields:
{json.dumps(basic_fields, indent=2)}

2) Old resume text (if provided):
\"\"\"{old_resume_text}\"\"\"

3) LinkedIn profile (if provided):
\"\"\"{linkedin_profile}\"\"\"

Return a JSON object with this structure:
{{
  "name": "...",
  "headline": "...",
  "contact": "...",
  "location": "...",
  "links": {{
    "linkedin": "...",
    "portfolio": "..."
  }},
  "education": [
    {{
      "degree": "...",
      "institution": "...",
      "start_year": "...",
      "end_year": "...",
      "details": "..."
    }}
  ],
  "experience": [
    {{
      "title": "...",
      "company": "...",
      "location": "...",
      "start_date": "...",
      "end_date": "...",
      "bullets": ["...", "..."]
    }}
  ],
  "projects": [
    {{
      "name": "...",
      "tech_stack": ["..."],
      "bullets": ["...", "..."]
    }}
  ],
  "skills": ["..."],
  "achievements": ["..."]
}}

- Fill in missing fields with best guesses from the texts.
- Keep dates and chronology as accurate as possible.
- Only output JSON, no explanations.
"""

    model = _get_model()
    response = model.generate_content(prompt)
    text = (response.text or "").strip()

    try:
        return json.loads(text)
    except Exception:
        cleaned = (
            text.replace("```json", "")
            .replace("```", "")
            .replace("`", "")
            .strip()
        )
        return json.loads(cleaned)


def match_profile_to_job(profile: dict, target_role: str, job_description: str) -> dict:
    """
    Step 3: Job Role & Keyword Matching (ATS Optimization)
    """
    prompt = f"""
You are an ATS optimization assistant.

Profile JSON:
{json.dumps(profile, indent=2)}

Target role: {target_role}

Job description:
\"\"\"{job_description}\"\"\"

Tasks:
1. Identify top skills/keywords from the job description.
2. Update the profile to highlight matching skills and experience
   (do NOT invent fake experience).
3. Update:
   - "skills"
   - "experience[*].bullets"
   - "projects[*].bullets"
   to be ATS-friendly and naturally include important keywords.

Return ONLY the updated profile JSON with the same structure.
"""

    model = _get_model()
    response = model.generate_content(prompt)
    cleaned = _clean_gemini_json(response.text or "{}")
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Gemini evaluation failed.")
    return data


def create_resume_from_profile(profile: dict, tone: str, template_style: str) -> str:
    """
    Steps 4 & 5: Content Generation & Formatting
    """
    prompt = f"""
You are an expert resume writer and ATS specialist.

Create a professional resume in plain text from this profile JSON:
{json.dumps(profile, indent=2)}

Formatting:
- Put the candidate name as a large header at the top.
- Next line: contact info and links (email | phone | location | LinkedIn | portfolio if present).
- Use section headings in ALL CAPS:
  SUMMARY
  SKILLS
  EXPERIENCE
  PROJECTS
  EDUCATION
  ACHIEVEMENTS (only if present)
- Use '-' bullet points under EXPERIENCE and PROJECTS.
- Tone should be {tone}.
- Layout style (template_style): {template_style}
  - "classic": traditional resume
  - "modern": slightly more stylish language
  - "minimal": clean and concise

Return ONLY the resume text, no explanations.
"""

    model = _get_model()
    response = model.generate_content(prompt)
    return (response.text or "").strip()


def polish_resume_text(resume_text: str) -> str:
    """
    Step 6: Grammar, Style & Consistency Check
    """
    prompt = f"""
You are a grammar and style corrector.

Improve the following resume text:
- Fix grammar, spelling, and punctuation.
- Ensure consistent tense (past roles in past tense, current role in present tense).
- Avoid redundant repetitions.
- Keep the same structure and sections; do not invent new jobs or projects.

Resume:
\"\"\"{resume_text}\"\"\"

Return ONLY the corrected resume text.
"""

    model = _get_model()
    response = model.generate_content(prompt)
    return (response.text or "").strip()


def full_resume_pipeline(
    name,
    headline,
    contact,
    location,
    linkedin,
    portfolio,
    education,
    experience,
    projects,
    skills,
    achievements,
    target_role,
    job_description,
    tone,
    template_style,
    old_resume_text="",
    linkedin_profile="",
) -> str:
    """
    Combine all steps of the resume pipeline.
    """
    basic_fields = {
        "name": name,
        "headline": headline,
        "contact": contact,
        "location": location,
        "linkedin": linkedin,
        "portfolio": portfolio,
        "education": education,
        "experience": experience,
        "projects": projects,
        "skills": skills,
        "achievements": achievements,
    }

    profile = extract_profile_from_sources(
        basic_fields=basic_fields,
        old_resume_text=old_resume_text,
        linkedin_profile=linkedin_profile,
    )

    if job_description.strip() or target_role.strip():
        profile = match_profile_to_job(profile, target_role, job_description)

    raw_resume = create_resume_from_profile(profile, tone, template_style)
    final_resume = polish_resume_text(raw_resume)
    return final_resume


# ------------------ RESUME ROUTES ------------------


@app.route("/", methods=["GET"])
def home():
    return render_template("home.html")


@app.route("/resume", methods=["GET", "POST"])
def resume_builder():
    resume_output = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        headline = request.form.get("headline", "").strip()
        contact = request.form.get("contact", "").strip()
        location = request.form.get("location", "").strip()
        linkedin = request.form.get("linkedin", "").strip()
        portfolio = request.form.get("portfolio", "").strip()
        education = request.form.get("education", "").strip()
        experience = request.form.get("experience", "").strip()
        projects = request.form.get("projects", "").strip()
        skills = request.form.get("skills", "").strip()
        achievements = request.form.get("achievements", "").strip()
        target_role = request.form.get("target_role", "").strip()
        job_description = request.form.get("job_description", "").strip()
        tone = request.form.get("tone", "corporate").strip()
        template_style = request.form.get("template_style", "classic").strip()
        linkedin_profile = request.form.get("linkedin_profile", "").strip()

        old_resume_text = ""
        old_resume_file = request.files.get("old_resume")
        if old_resume_file and old_resume_file.filename:
            old_resume_text = old_resume_file.read().decode("utf-8", errors="ignore")

        resume_output = full_resume_pipeline(
            name=name,
            headline=headline,
            contact=contact,
            location=location,
            linkedin=linkedin,
            portfolio=portfolio,
            education=education,
            experience=experience,
            projects=projects,
            skills=skills,
            achievements=achievements,
            target_role=target_role,
            job_description=job_description,
            tone=tone,
            template_style=template_style,
            old_resume_text=old_resume_text,
            linkedin_profile=linkedin_profile,
        )

        session["last_resume_text"] = resume_output
        session["last_resume_name"] = name or "resume"

    return render_template("resume/resume.html", resume_output=resume_output)


@app.route("/resume/download", methods=["GET"])
def download_resume():
    resume_text = session.get("last_resume_text")
    name = session.get("last_resume_name", "resume")

    if not resume_text:
        return redirect(url_for("resume_builder"))

    safe_name = "_".join(name.strip().split()).lower() or "resume"
    filename = f"{safe_name}.txt"

    buffer = BytesIO()
    buffer.write(resume_text.encode("utf-8"))
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="text/plain",
        as_attachment=True,
        download_name=filename,
    )


# ==========================================================
#             VIDEO-CALL STYLE MOCK INTERVIEW
# ==========================================================

def generate_question_set(user_profile: dict, count: int = 10) -> list:
    """
    Generate interview questions tailored to the candidate profile.
    """
    prompt = f"""
You are an experienced interviewer. Generate {count} realistic questions tailored to this candidate.

Candidate profile:
{json.dumps(user_profile, indent=2)}

Return ONLY JSON array in this schema:
[
  {{
    "question": "question text",
    "category": "behavioral | technical | hr | coding",
    "difficulty": "easy | medium | hard",
    "guidance": "short notes on what to mention"
  }}
]

Rules:
- Align topics with the role, experience, and job description.
- Mix categories if style is "General".
- Do not add markdown fences or commentary.
"""

    model = _get_model()
    response = model.generate_content(prompt)
    cleaned = _clean_gemini_json(response.text or "[]")
    raw_questions = json.loads(cleaned)
    if not isinstance(raw_questions, list):
        raise ValueError("Gemini did not return a list of questions.")

    normalized = []
    for idx, item in enumerate(raw_questions, start=1):
        question_text = item.get("question") or item.get("text")
        if not question_text:
            continue
        normalized.append({
            "id": item.get("id") or f"q{idx}",
            "question": question_text.strip(),
            "category": (item.get("category") or "general").lower(),
            "difficulty": (item.get("difficulty") or "medium").lower(),
            "guidance": item.get("guidance", ""),
        })

    if not normalized:
        raise ValueError("Gemini returned no usable questions.")
    return normalized[:count]


def evaluate_interview_answer(question: dict, answer: str, user_profile: dict) -> dict:
    """
    Evaluate an answer and return rating/feedback JSON.
    """
    prompt = f"""
You are an AI interview coach.

User profile:
{json.dumps(user_profile, indent=2)}

Question:
{json.dumps(question, indent=2)}

Candidate Answer:
\"\"\"{answer}\"\"\"

Return ONLY JSON with this schema:
{{
  "rating": 3,
  "feedback": "Short constructive paragraph",
  "correct_answer": "Key points an ideal answer should include",
  "followup_question": "Optional follow-up question or null"
}}

Rating must be an integer 1-5.
"""

    model = _get_model()
    response = model.generate_content(prompt)
    cleaned = _clean_gemini_json(response.text or "{}")
    result = json.loads(cleaned)
    if not isinstance(result, dict):
        raise ValueError("Gemini returned invalid evaluation.")
    result.setdefault("rating", 3)
    result.setdefault("feedback", "No detailed feedback provided.")
    result.setdefault("correct_answer", "Not available.")
    result.setdefault("followup_question", None)
    return result


# ------------------ INTERVIEW SIM ROUTES ------------------


@app.route("/interview-sim", methods=["GET"])
def interview_sim_page():
    """
    Renders the video-call style mock interview page.
    """
    return render_template("interview-sim.html")


@app.route("/api/interview/start", methods=["POST"])
def api_interview_start():
    """
    Start a new interview session: generate question set.
    """
    data = request.get_json()
    name = data.get("name", "")
    role = data.get("role", "")
    experience = data.get("experience", "Fresher")
    style = data.get("style", "General")
    job_description = data.get("job_description", "")
    resume_text = data.get("resume_text", "")

    user_profile = {
        "name": name,
        "role": role,
        "experience": experience,
        "style": style,
        "job_description": job_description,
        "resume_text": resume_text,
    }

    try:
        questions = generate_question_set(user_profile)
    except Exception as exc:  # pylint: disable=broad-except
        return jsonify({"error": f"Unable to generate questions: {exc}"}), 500

    if not questions:
        return jsonify({"error": "No questions generated."}), 500

    interview_state = {
        "profile": user_profile,
        "questions": questions,
        "current_index": 0,
        "history": [],
    }
    session["live_interview"] = interview_state

    first_question = questions[0]

    return jsonify({
        "total_questions": len(questions),
        "question_index": 0,
        "question": first_question,
    })


@app.route("/api/interview/submit-answer", methods=["POST"])
def api_interview_submit_answer():
    """
    Evaluate answer for current question.
    """
    data = request.get_json() or {}
    question_id = data.get("question_id")
    answer = (data.get("answer") or "").strip()

    if not question_id or not answer:
        return jsonify({"error": "Question ID and answer are required."}), 400

    state = session.get("live_interview")
    if not state:
        return jsonify({"error": "No active interview session."}), 400

    questions = state.get("questions", [])
    question = next((q for q in questions if q.get("id") == question_id), None)
    if not question:
        return jsonify({"error": "Question not found."}), 404

    try:
        evaluation = evaluate_interview_answer(question, answer, state["profile"])
    except Exception as exc:  # pylint: disable=broad-except
        return jsonify({"error": f"Unable to evaluate answer: {exc}"}), 500

    history = state.setdefault("history", [])
    history.append({
        "question_id": question_id,
        "answer": answer,
        "evaluation": evaluation,
    })
    session["live_interview"] = state

    return jsonify({"evaluation": evaluation})


@app.route("/api/interview/next-question", methods=["POST"])
def api_interview_next_question():
    """
    Fetch next question or generate more.
    """
    state = session.get("live_interview")
    if not state:
        return jsonify({"error": "No active interview session."}), 400

    current_index = state.get("current_index", 0) + 1
    questions = state.get("questions", [])

    if current_index >= len(questions):
        try:
            fresh_questions = generate_question_set(state["profile"])
        except Exception as exc:  # pylint: disable=broad-except
            return jsonify({"error": f"Unable to fetch more questions: {exc}"}), 500
        offset = len(questions)
        for idx, q in enumerate(fresh_questions, start=1):
            if not q.get("id"):
                q["id"] = f"q{offset + idx}"
        questions.extend(fresh_questions)
        state["questions"] = questions

    state["current_index"] = current_index
    session["live_interview"] = state

    question = questions[current_index]
    return jsonify({
                "total_questions": len(questions),
        "question_index": current_index,
        "question": question,
    })


# ==========================================================
#                SKILL ASSESSMENT (QUIZ + Q&A)
# ==========================================================


def _clean_gemini_json(text: str) -> str:
    """Strip Markdown fences from Gemini responses."""
    cleaned = (text or "").strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()
    return cleaned


def _generate_ai_questions(filters: dict) -> list:
    """
    Call Gemini to generate quiz/interview questions.

    filters keys:
      mode: quiz|interview
      num_questions: int (<=15)
      company, technology, role, difficulty, question_type
    """
    mode = filters.get("mode", "quiz").lower()
    num_questions = max(1, min(int(filters.get("num_questions", 5)), 15))
    company = filters.get("company") or "Any company"
    technology = filters.get("technology") or "General technology"
    role = filters.get("role") or "Any role"
    difficulty = (filters.get("difficulty") or "Mixed").lower()
    question_type = filters.get("question_type") or ("MCQ" if mode == "quiz" else "Theory")
    keywords = filters.get("search_text") or "None"

    quiz_schema = """
[
  {
    "id": "q1",
    "question": "Question text",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_option_index": 1,
    "explanation": "1-2 sentence reasoning",
    "difficulty": "easy|medium|hard",
    "topic": "DSA / SQL / ...",
    "company": "TCS",
    "role": "SDE"
  }
]
""".strip()

    interview_schema = """
[
  {
    "id": "q1",
    "question": "Behavioral or technical question text",
    "model_answer": "High-level model answer highlighting key points.",
    "difficulty": "easy|medium|hard",
    "topic": "DSA / Behavioral / ...",
    "company": "TCS",
    "role": "SDE"
  }
]
""".strip()

    prompt = f"""
You are an expert interviewer helping candidates practice.

Generate {num_questions} distinct questions for:
- Company focus: {company}
- Technology/topic focus: {technology}
- Target role: {role}
- Difficulty preference: {difficulty}
- Question type requested: {question_type}
- Mode: {"Quiz/MCQ" if mode == "quiz" else "Interview coaching"}
- Extra keywords or constraints: {keywords}

Rules:
- Questions must be realistic for {role} roles at {company}.
- Difficulty labels must be lower-case: easy/medium/hard.
- If mode=quiz, ALWAYS output exactly 4 options, craft non-trivial distractors,
  and set correct_option_index (0-based integer referring to options array).
- If mode=interview, include a concise model_answer that outlines what a good response should cover.
- Return ONLY valid JSON. Do not wrap the JSON in markdown fences or commentary.

Expected JSON format:
{quiz_schema if mode == "quiz" else interview_schema}
"""

    model = _get_model()
    response = model.generate_content(prompt)
    cleaned = _clean_gemini_json(response.text or "[]")
    questions = json.loads(cleaned)

    if not isinstance(questions, list):
        raise ValueError("Gemini did not return a list of questions.")

    return questions[:num_questions]


def _evaluate_interview_answers(entries: list) -> list:
    """
    Ask Gemini to review user answers vs. model answers.
    entries: [{id, question, model_answer, user_answer}]
    """
    prompt_payload = json.dumps(entries, indent=2)
    prompt = f"""
You are an interview coach. For each entry in the JSON array below, compare the
candidate answer to the provided model answer. Provide structured feedback.

Entries:
{prompt_payload}

Return JSON array with the same order, using this schema (no markdown, just JSON):
[
  {{
    "id": "q1",
    "rating": 1,
    "verdict": "Improve | Fair | Strong",
    "feedback": "Short constructive paragraph",
    "strengths": ["bullet", "..."],
    "improvements": ["bullet", "..."]
  }}
]

Rating must be an integer 1-5.
"""
    model = _get_model()
    response = model.generate_content(prompt)
    cleaned = _clean_gemini_json(response.text or "[]")
    evaluations = json.loads(cleaned)
    if not isinstance(evaluations, list):
        raise ValueError("Gemini did not return a list of evaluations.")
    return evaluations


@app.route("/skills", methods=["GET"])
def skills_page():
    return render_template("skills/skills.html")


@app.route("/api/generate_questions", methods=["POST"])
def api_generate_questions():
    """
    Generate quiz/interview questions via Gemini based on user filters.
    """
    data = request.get_json() or {}
    mode = (data.get("mode") or "quiz").lower()
    if mode not in ("quiz", "interview"):
        return jsonify({"error": "Invalid mode."}), 400

    try:
        questions = _generate_ai_questions(data)
    except Exception as exc:  # pylint: disable=broad-except
        return jsonify({"error": f"Unable to generate questions: {exc}"}), 500

    skills_state = session.get("skills_session", {})
    skills_state[mode] = questions
    session["skills_session"] = skills_state

    return jsonify({"mode": mode, "questions": questions})


@app.route("/api/grade_quiz", methods=["POST"])
def api_grade_quiz():
    """
    Grade MCQ answers against the last generated quiz questions.
    """
    payload = request.get_json() or {}
    answers = payload.get("answers", [])

    skills_state = session.get("skills_session", {})
    quiz_questions = skills_state.get("quiz")
    if not quiz_questions:
        return jsonify({"error": "No quiz questions available. Generate questions first."}), 400

    question_map = {q["id"]: q for q in quiz_questions if "correct_option_index" in q}
    total = len(question_map)
    if total == 0:
        return jsonify({"error": "Quiz questions missing answer keys."}), 500

    correct = 0
    results = []
    for ans in answers:
        qid = ans.get("id")
        selected = ans.get("selected_option_index")
        q = question_map.get(qid)
        if not q:
            continue
        is_correct = selected == q.get("correct_option_index")
        if is_correct:
            correct += 1
        results.append({
            "id": qid,
            "question": q.get("question"),
            "options": q.get("options", []),
            "selected_option_index": selected,
            "correct_option_index": q.get("correct_option_index"),
            "is_correct": is_correct,
            "explanation": q.get("explanation", ""),
        })

    return jsonify({
        "score": correct,
        "total": total,
        "accuracy": (correct / total * 100) if total else 0,
        "results": results,
    })


@app.route("/api/review_interview_answers", methods=["POST"])
def api_review_interview_answers():
    """
    Send interview answers to Gemini for evaluation.
    """
    payload = request.get_json() or {}
    answers = payload.get("answers", [])
    skills_state = session.get("skills_session", {})
    interview_questions = skills_state.get("interview")
    if not interview_questions:
        return jsonify({"error": "No interview questions available. Generate questions first."}), 400

    question_map = {q["id"]: q for q in interview_questions}
    entries = []
    for ans in answers:
        qid = ans.get("id")
        user_answer = (ans.get("answer") or "").strip()
        q = question_map.get(qid)
        if not q:
            continue
        entries.append({
            "id": qid,
            "question": q.get("question"),
            "model_answer": q.get("model_answer", ""),
            "user_answer": user_answer or "User skipped this question.",
        })

    if not entries:
        return jsonify({"error": "No valid answers to review."}), 400

    try:
        evaluations = _evaluate_interview_answers(entries)
    except Exception as exc:  # pylint: disable=broad-except
        return jsonify({"error": f"Unable to review answers: {exc}"}), 500

    return jsonify({"evaluations": evaluations})

# ==========================================================
#                     DASHBOARD API
# ==========================================================

@app.route("/api/dashboard/summary", methods=["GET"])
def api_dashboard_summary():
    """
    Returns overall summary for the dashboard home.
    For now, uses simple static/sample data.
    Later you can compute from DB/session.
    """
    # Example data – replace with real stats later if you store them
    user_profile = {
        "name": "Demo User",
        "email": "demo@example.com",
        "target_role": "Software Engineer",
        "experience_level": "Fresher",
        "profile_completion": 0.7,  # 70%
        "resumes_built": 3,
        "interviews_taken": 5,
        "quizzes_completed": 8,
    }

    metrics = {
        "resume": {
            "last_score": 82,
            "ats_score": 78,
            "count": 3,
            "status": "ATS Optimized",
        },
        "interview": {
            "last_overall": 7.5,
            "by_category": {
                "content": 8.0,
                "technical": 7.0,
                "behavioral": 7.5,
                "communication": 8.5,
            },
            # small history for chart
            "history": [
                {"label": "Session 1", "score": 6.5},
                {"label": "Session 2", "score": 7.0},
                {"label": "Session 3", "score": 7.8},
                {"label": "Session 4", "score": 8.1},
            ],
        },
        "quiz": {
            "accuracy": 74,
            "best_topics": ["SQL", "OOPS"],
            "weak_topics": ["OS", "Aptitude"],
            "history": [
                {"label": "Quiz 1", "accuracy": 65},
                {"label": "Quiz 2", "accuracy": 72},
                {"label": "Quiz 3", "accuracy": 78},
                {"label": "Quiz 4", "accuracy": 80},
            ],
        },
    }

    recent_activity = [
        {
            "type": "quiz",
            "title": "DBMS & SQL Quiz",
            "timestamp": "2025-11-23 20:15",
            "details": "Scored 8/10 (80%)",
        },
        {
            "type": "interview",
            "title": "Mock Interview – SDE @ TCS",
            "timestamp": "2025-11-22 18:05",
            "details": "Overall score: 7.8/10",
        },
        {
            "type": "resume",
            "title": "Resume for Data Analyst Role",
            "timestamp": "2025-11-21 15:40",
            "details": "ATS optimized with keywords.",
        },
    ]

    badges = [
        {"id": 1, "label": "Consistency Star", "description": "Practiced 5 days in a row"},
        {"id": 2, "label": "Quiz Master", "description": "Completed 10+ quizzes"},
        {"id": 3, "label": "Interview Explorer", "description": "Tried 3 different roles"},
    ]

    return jsonify({
        "user": user_profile,
        "metrics": metrics,
        "activity": recent_activity,
        "badges": badges,
    })


@app.route("/api/user/profile", methods=["GET", "POST"])
def api_user_profile():
    """
    Very simple profile endpoint just for the dashboard UI.
    Replace with real DB logic when you add authentication.
    """
    if request.method == "POST":
        data = request.get_json()
        # Here you would save to DB.
        # For now just echo back.
        return jsonify({"status": "ok", "profile": data})

    # GET: return sample profile
    return jsonify({
        "name": "Demo User",
        "email": "demo@example.com",
        "target_role": "Software Engineer",
        "experience_level": "Fresher",
        "linkedin": "https://www.linkedin.com/in/demo",
        "resume_uploaded": True,
    })

# ------------------ MAIN ------------------

if __name__ == "__main__":
    print("Template folder Flask is using:", app.template_folder)
    app.run(debug=True)
