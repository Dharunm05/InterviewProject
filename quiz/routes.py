from flask import Blueprint, render_template, request, jsonify
from .data import QUESTIONS
from .services import filter_questions

quiz_bp = Blueprint("quiz", __name__, template_folder="../templates/quiz")

@quiz_bp.route("/", methods=["GET"])
def config():
    # Render config/filter page
    return render_template("quiz/config.html")

@quiz_bp.route("/start", methods=["POST"])
def start_quiz():
    mode = request.form.get("mode")  # quiz / interview
    company = request.form.get("company")
    tech = request.form.get("tech")
    difficulty = request.form.get("difficulty")
    num_q = int(request.form.get("numQuestions", 10))

    selected = filter_questions(QUESTIONS, company, tech, difficulty, num_q)

    if mode == "quiz":
        return render_template("quiz/session.html", questions=selected, mode="quiz")
    else:
        return render_template("quiz/session.html", questions=selected, mode="interview")

@quiz_bp.route("/submit-quiz", methods=["POST"])
def submit_quiz():
    data = request.json
    answers = data.get("answers", [])
    questions = data.get("questions", [])

    score = 0
    detailed = []
    for q, ans_index in zip(questions, answers):
        correct = q["correct_option"]
        is_correct = (ans_index == correct)
        if is_correct:
            score += 1
        detailed.append({
            "question_text": q["question_text"],
            "your_answer": q["options"][ans_index] if ans_index is not None else None,
            "correct_answer": q["options"][correct],
            "is_correct": is_correct,
            "explanation": q.get("explanation")
        })

    return jsonify({
        "score": score,
        "total": len(questions),
        "details": detailed
    })
