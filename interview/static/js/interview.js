document.addEventListener("DOMContentLoaded", () => {
  const formFields = {
    name: document.getElementById("candidateName"),
    role: document.getElementById("candidateRole"),
    experience: document.getElementById("candidateExperience"),
    style: document.getElementById("candidateStyle"),
    jobDescription: document.getElementById("jobDescription"),
    resumeSummary: document.getElementById("resumeSummary"),
  };

  const ui = {
    questionText: document.getElementById("questionText"),
    questionMeta: document.getElementById("questionMeta"),
    questionCounter: document.getElementById("questionCounter"),
    feedbackBox: document.getElementById("feedbackBox"),
    transcriptBox: document.getElementById("transcriptBox"),
    answerBox: document.getElementById("answerBox"),
    ratingBadge: document.getElementById("ratingBadge"),
    recordingIndicator: document.getElementById("recordingIndicator"),
    statusMessage: document.getElementById("statusMessage"),
    cameraStatus: document.getElementById("cameraStatus"),
    videoEl: document.getElementById("interviewVideo"),
    buttons: {
      start: document.getElementById("btnStartInterview"),
      record: document.getElementById("btnRecord"),
      stopSend: document.getElementById("btnStopSend"),
      next: document.getElementById("btnNextQuestion"),
      skip: document.getElementById("btnSkipQuestion"),
      end: document.getElementById("btnEndInterview"),
    },
  };

  const state = {
    interviewActive: false,
    currentQuestion: null,
    totalQuestions: 0,
    speechSupported: false,
    recognition: null,
    isRecording: false,
    transcriptBuffer: "",
  };

  initCamera();
  initSpeechRecognition();
  wireEvents();
  updateInteractionState(false);

  function wireEvents() {
    ui.buttons.start.addEventListener("click", startInterview);
    ui.buttons.record.addEventListener("click", startRecording);
    ui.buttons.stopSend.addEventListener("click", async () => {
      await stopRecording();
      submitAnswer();
    });
    ui.buttons.next.addEventListener("click", () => {
      if (!state.interviewActive) {
        return;
      }
      loadNextQuestion();
    });
    ui.buttons.skip.addEventListener("click", () => {
      ui.answerBox.value = "";
      ui.transcriptBox.textContent = "Question skipped. Loading the next one...";
      loadNextQuestion();
    });
    ui.buttons.end.addEventListener("click", () => {
      resetInterview("Interview ended. Feel free to start again.");
    });
  }

  function setStatus(message, tone = "muted") {
    ui.statusMessage.textContent = message || "";
    ui.statusMessage.className = `small text-${tone}`;
  }

  function updateInteractionState(enabled) {
    const btns = ["record", "stopSend", "next", "skip", "end"];
    btns.forEach((key) => {
      ui.buttons[key].disabled = !enabled;
    });
    if (!state.speechSupported) {
      ui.buttons.record.disabled = true;
      ui.buttons.stopSend.disabled = true;
      ui.recordingIndicator.textContent = "No Mic";
      ui.recordingIndicator.className = "badge bg-secondary";
    }
  }

  async function startInterview() {
    const payload = {
      name: formFields.name.value.trim(),
      role: formFields.role.value.trim(),
      experience: formFields.experience.value,
      style: formFields.style.value,
      job_description: formFields.jobDescription.value.trim(),
      resume_text: formFields.resumeSummary.value.trim(),
    };

    setStatus("Generating interview questions...", "primary");
    ui.buttons.start.disabled = true;

    try {
      const res = await fetch("/api/interview/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Unable to start interview.");
      }
      state.interviewActive = true;
      state.currentQuestion = data.question;
      state.totalQuestions = data.total_questions || 0;
      state.interviewIndex = data.question_index || 0;
      renderQuestion(data.question, data.question_index, data.total_questions);
      ui.feedbackBox.textContent = "After you answer, AI feedback will appear here.";
      ui.transcriptBox.textContent = "Listening ready. Press 🎤 Start Recording when you are ready.";
      ui.answerBox.value = "";
      updateInteractionState(true);
      setStatus("Interview in progress. Answer the question when ready.", "success");
    } catch (err) {
      console.error(err);
      setStatus(err.message, "danger");
      ui.buttons.start.disabled = false;
    }
  }

  function renderQuestion(question, index = 0, total = 0) {
    if (!question) {
      ui.questionText.textContent = "Waiting for the next question...";
      ui.questionMeta.textContent = "";
      ui.questionCounter.textContent = "Q - / -";
      return;
    }
    state.currentQuestion = question;
    ui.questionText.textContent = question.question || "Question unavailable.";
    const metaPieces = [];
    if (question.category) metaPieces.push(`Category: ${capitalize(question.category)}`);
    if (question.difficulty) metaPieces.push(`Difficulty: ${capitalize(question.difficulty)}`);
    if (question.guidance) metaPieces.push(`Focus: ${question.guidance}`);
    ui.questionMeta.textContent = metaPieces.join(" • ");
    ui.questionCounter.textContent = `Q ${index + 1} / ${total || state.totalQuestions}`;
    ui.answerBox.value = "";
    ui.recordingIndicator.textContent = "Idle";
    ui.recordingIndicator.className = "badge bg-secondary";
  }

  function capitalize(str) {
    return str ? str.charAt(0).toUpperCase() + str.slice(1) : "";
  }

  function initCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
      ui.cameraStatus.textContent = "Camera Unsupported";
      ui.cameraStatus.className = "badge bg-secondary";
      return;
    }
    navigator.mediaDevices
      .getUserMedia({ video: true, audio: false })
      .then((stream) => {
        ui.videoEl.srcObject = stream;
        ui.cameraStatus.textContent = "Camera On";
        ui.cameraStatus.className = "badge bg-success-subtle text-success";
      })
      .catch(() => {
        ui.cameraStatus.textContent = "Camera Blocked";
        ui.cameraStatus.className = "badge bg-danger-subtle text-danger";
      });
  }

  function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      ui.transcriptBox.textContent = "Speech recognition is not supported in this browser. Please type your answers.";
      return;
    }
    state.speechSupported = true;
    state.recognition = new SpeechRecognition();
    state.recognition.lang = navigator.language || "en-US";
    state.recognition.continuous = true;
    state.recognition.interimResults = true;

    state.recognition.onstart = () => {
      state.transcriptBuffer = "";
      ui.recordingIndicator.textContent = "Recording...";
      ui.recordingIndicator.className = "badge bg-danger";
      ui.transcriptBox.textContent = "Listening...";
    };

    state.recognition.onerror = (event) => {
      console.warn("Speech recognition error", event);
      setStatus("Microphone error: " + (event.error || "unknown"), "danger");
      stopRecording();
    };

    state.recognition.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const { transcript } = event.results[i][0];
        if (event.results[i].isFinal) {
          state.transcriptBuffer += transcript + " ";
        } else {
          interim = transcript;
        }
      }
      const combined = (state.transcriptBuffer + interim).trim();
      ui.answerBox.value = combined;
      ui.transcriptBox.textContent = combined || "Listening...";
    };

    state.recognition.onend = () => {
      if (state.isRecording) {
        state.recognition.start(); // auto restart if user hasn't stopped manually
        return;
      }
      ui.recordingIndicator.textContent = "Idle";
      ui.recordingIndicator.className = "badge bg-secondary";
    };
  }

  function startRecording() {
    if (!state.speechSupported || !state.recognition) {
      alert("Speech recognition not supported in this browser.");
      return;
    }
    if (!state.interviewActive || !state.currentQuestion) {
      setStatus("Start the interview before recording.", "danger");
      return;
    }
    if (state.isRecording) {
      return;
    }
    state.isRecording = true;
    state.recognition.start();
  }

  function stopRecording() {
    if (!state.isRecording || !state.recognition) {
      return Promise.resolve();
    }
    state.isRecording = false;
    return new Promise((resolve) => {
      const handleEnd = () => {
        state.recognition.removeEventListener("end", handleEnd);
        resolve();
      };
      state.recognition.addEventListener("end", handleEnd);
      state.recognition.stop();
    });
  }

  async function submitAnswer() {
    if (!state.interviewActive || !state.currentQuestion) {
      setStatus("No active question to answer.", "danger");
      return;
    }
    const answer = ui.answerBox.value.trim();
    if (!answer) {
      setStatus("Please provide an answer before sending.", "danger");
      return;
    }

    setStatus("Evaluating your answer...", "primary");
    updateInteractionState(false);

    try {
      const res = await fetch("/api/interview/submit-answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question_id: state.currentQuestion.id,
          answer,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Evaluation failed.");
      }

      displayFeedback(data.evaluation);
      setStatus("Answer evaluated. Loading the next question...", "success");
      setTimeout(() => {
        loadNextQuestion();
      }, 1200);
    } catch (err) {
      console.error(err);
      setStatus(err.message, "danger");
      updateInteractionState(true);
    }
  }

  function displayFeedback(evaluation = {}) {
    const rating = evaluation.rating ?? "—";
    ui.ratingBadge.textContent = `Rating: ${rating}`;
    ui.ratingBadge.className = rating >= 4 ? "badge bg-success" : rating >= 2 ? "badge bg-warning" : "badge bg-danger";

    const lines = [];
    if (evaluation.feedback) {
      lines.push(`Feedback:\n${evaluation.feedback}`);
    }
    if (evaluation.correct_answer) {
      lines.push(`Ideal Answer:\n${evaluation.correct_answer}`);
    }
    if (evaluation.followup_question) {
      lines.push(`Follow-up Question:\n${evaluation.followup_question}`);
    }
    ui.feedbackBox.textContent = lines.join("\n\n") || "No feedback returned.";
  }

  async function loadNextQuestion() {
    if (!state.interviewActive) {
      return;
    }
    try {
      const res = await fetch("/api/interview/next-question", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Unable to fetch next question.");
      }
      state.totalQuestions = data.total_questions || state.totalQuestions;
      renderQuestion(data.question, data.question_index, data.total_questions);
      ui.answerBox.value = "";
      ui.transcriptBox.textContent = "Press 🎤 Start Recording when you are ready.";
      setStatus("Next question loaded.", "primary");
      updateInteractionState(true);
    } catch (err) {
      console.error(err);
      setStatus(err.message, "danger");
      updateInteractionState(true);
    }
  }

  function resetInterview(message) {
    state.interviewActive = false;
    state.currentQuestion = null;
    state.totalQuestions = 0;
    ui.questionText.textContent = "Interview ended.";
    ui.questionMeta.textContent = "";
    ui.questionCounter.textContent = "Q 0 / 0";
    ui.feedbackBox.textContent = "After you answer, AI feedback will appear here.";
    ui.transcriptBox.textContent = "Press 🎤 Start Recording to capture your answer.";
    ui.answerBox.value = "";
    updateInteractionState(false);
    ui.buttons.start.disabled = false;
    setStatus(message || "Interview reset.", "secondary");
  }
});

