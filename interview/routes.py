from flask import Blueprint, render_template, request, jsonify
from .services import generate_questions, evaluate_answer

interview_bp = Blueprint("interview", __name__, template_folder="../templates/interview")

@interview_bp.route("/", methods=["GET"])
def setup():
    return render_template("interview/setup.html")

@interview_bp.route("/start", methods=["POST"])
def start_interview():
    data = request.form  # from HTML form
    role = data.get("role")
    experience = data.get("experience")
    jd = data.get("jobDescription")
    interview_type = data.get("interviewType")  # HR / Technical / Behavioral
    num_questions = int(data.get("numQuestions", 5))

    questions = generate_questions(role, experience, jd, interview_type, num_questions)
    # Pass questions list to template (or store in session)
    return render_template("interview/session.html", questions=questions, role=role, jd=jd)

@interview_bp.route("/evaluate", methods=["POST"])
def evaluate():
    data = request.json
    question = data.get("question")
    answer = data.get("answer")
    role = data.get("role")
    jd = data.get("jobDescription")

    result = evaluate_answer(question, answer, role, jd)
    return jsonify(result)
