from flask import Blueprint, render_template, request, current_app, jsonify
from .services import generate_resume

resume_bp = Blueprint("resume", __name__, template_folder="../templates/resume")

@resume_bp.route("/", methods=["GET"])
def resume_form():
    return render_template("resume/form.html")

@resume_bp.route("/generate", methods=["POST"])
def resume_generate():
    data = request.json  # expecting JSON from JS
    resume_result = generate_resume(
        personal_info=data.get("personalInfo"),
        education=data.get("education"),
        experience=data.get("experience"),
        skills=data.get("skills"),
        target_role=data.get("targetRole"),
        job_description=data.get("jobDescription"),
        tone=data.get("tone", "corporate"),
    )
    return jsonify(resume_result)
