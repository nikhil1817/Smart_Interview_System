import { useEffect, useRef, useState } from "react";
import { useAudio } from "../hooks/useAudio";
import { useModelInference } from "../hooks/useModelInference";
import { parseResumeFile } from "../services/apiService";

const ROLES = [
  // Engineering
  "SWE",
  "Frontend Engineer",
  "Backend Engineer",
  "Full-Stack Engineer",
  "Mobile Engineer (iOS/Android)",
  "Embedded / Systems Engineer",
  "ML Engineer",
  "AI Research Engineer",
  "Data Engineer",
  "Data Scientist",
  "Data Analyst",
  "DevOps / SRE",
  "Platform Engineer",
  "Security Engineer",
  "QA / SDET",
  "Engineering Manager",
  // Product & Design
  "Product Manager",
  "Technical Program Manager",
  "UX Designer",
  "UX Researcher",
  "Product Designer",
  // Business & Operations
  "Business Analyst",
  "Solutions Architect",
  "Cloud Architect",
  "Sales Engineer",
  "Customer Success Manager",
  "Operations Manager",
  // Finance & Strategy
  "Finance Analyst",
  "Strategy Consultant",
  "Marketing Manager"
];

const QUESTION_TYPES = [
  "Behavioral",
  "Technical",
  "System Design",
  "LeetCode/DSA",
  "Culture Fit",
  "Mixed",
  "Leadership & Management",
  "Product Sense",
  "Estimation / Fermi",
  "Case Study",
  "Conflict Resolution",
  "Situational (STAR)",
  "Domain Knowledge",
  "Open-Ended / Vision"
];

const INTERVIEW_MODES = [
  "Standard",
  "Panel",
  "Stress",
  "Speed Round",
  "Deep Dive",
  "Case Interview",
  "Reverse Interview",
  "Competency-Based",
  "Final Round",
  "Coffee Chat"
];

const VOICE_MODES = ["Text Only", "Hear Interviewer", "Speak Answer", "Both (Hear + Speak)"];

const INTERVIEWERS = {
  Standard: [
    "Friendly HR",
    "Neutral Recruiter",
    "Senior Engineer",
    "Hiring Manager",
    "Peer Interviewer",
    "Bar Raiser",
    "Director of Engineering",
    "VP of Product"
  ],
  Panel: [
    "3-Person Panel",
    "Cross-functional Panel",
    "All-Engineer Panel",
    "Exec + IC Panel",
    "Diversity Panel"
  ],
  Stress: [
    "Tough Critic",
    "Silent Evaluator",
    "Devil's Advocate",
    "Rapid Questioner",
    "Skeptical CTO",
    "Interrupting Senior"
  ],
  "Speed Round": ["Timer Mode", "Rapid Fire", "Lightning Round"],
  "Deep Dive": ["Principal Engineer", "Staff Engineer", "Domain Expert", "Architect"],
  "Case Interview": ["McKinsey-Style", "BCG-Style", "Product Case", "Technical Case"],
  "Reverse Interview": ["Startup Founder", "Open Source Lead", "Engineering Lead"],
  "Competency-Based": ["HR Specialist", "Structured Interviewer", "STAR Assessor"],
  "Final Round": ["C-Suite Executive", "Founder", "General Manager", "Head of Dept"],
  "Coffee Chat": ["Friendly Peer", "Alumni", "Recruiter Informational"]
};

const PANEL_PERSONAS = [
  { name: "Alex", role: "Senior Engineer", style: "technical, precise, skeptical" },
  { name: "Maya", role: "HR Director", style: "behavioral, empathetic, thorough" },
  { name: "Sam", role: "Engineering Manager", style: "strategic, leadership-focused, big-picture" },
  { name: "Priya", role: "Principal Engineer", style: "deep technical, systems-thinking, exacting" },
  { name: "Jordan", role: "Product Manager", style: "product sense, user-focused, clarifying" }
];

const STORAGE_KEY = "ai-interview-simulator-state";
const HISTORY_KEY = "ai-interview-simulator-history";
const VOICE_AUTO_STOP_MS = 45000;

function loadStoredJson(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (error) {
    return fallback;
  }
}

function summarizeResume(text) {
  if (!text.trim()) {
    return "";
  }

  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  const topLines = lines.slice(0, 4);
  const lower = text.toLowerCase();
  const skillKeywords = [
    "react",
    "node",
    "python",
    "fastapi",
    "aws",
    "docker",
    "kubernetes",
    "sql",
    "machine learning",
    "leadership"
  ].filter((keyword) => lower.includes(keyword));

  const bullets = [];

  if (topLines.length > 0) {
    bullets.push(`- Profile snapshot: ${topLines.join(" | ").slice(0, 180)}`);
  }

  if (skillKeywords.length > 0) {
    bullets.push(`- Likely strengths: ${skillKeywords.slice(0, 5).join(", ")}`);
  }

  if (/led|managed|owner|mentored/i.test(text)) {
    bullets.push("- Leadership signals detected in the resume content.");
  }

  if (/improved|reduced|increased|launched|built|designed/i.test(text)) {
    bullets.push("- Achievement-oriented language suggests measurable project impact.");
  }

  if (bullets.length === 0) {
    bullets.push("- Resume content loaded. Tailor the interview based on the pasted experience.");
  }

  return bullets.join("\n");
}

function toBackendMode(interviewMode) {
  if (interviewMode === "Panel") return "panel";
  if (interviewMode === "Stress") return "stress";
  if (interviewMode === "Speed Round") return "speed_round";
  return "standard";
}

function scoreColor(score) {
  if (score >= 8) return "#4ade80";
  if (score >= 6) return "#facc15";
  return "#f87171";
}

function feedbackTheme(score) {
  if (score === null || score === undefined) {
    return {
      bg: "#0f2818",
      border: "#16a34a44",
      accent: "#4ade80",
      text: "#a7f3d0",
      label: "📋 Feedback on your answer"
    };
  }
  if (score >= 8) {
    return {
      bg: "#0f2818",
      border: "#16a34a44",
      accent: "#4ade80",
      text: "#a7f3d0",
      label: "✅ Great answer!"
    };
  }
  if (score >= 5) {
    return {
      bg: "#1c1a08",
      border: "#ca8a0444",
      accent: "#facc15",
      text: "#fef08a",
      label: "⚠️ Decent — room to improve"
    };
  }
  return {
    bg: "#1e0a0a",
    border: "#dc262644",
    accent: "#f87171",
    text: "#fca5a5",
    label: "❌ Needs work"
  };
}

function buildAssistantPersona(interviewMode, interviewer, panelIndex, backendAgent) {
  if (interviewMode === "Panel") {
    return PANEL_PERSONAS[panelIndex % PANEL_PERSONAS.length];
  }

  return {
    name: interviewer,
    role: backendAgent || "Interviewer",
    style: interviewMode
  };
}

function buildResumeDataFromText(text) {
  if (!text.trim()) {
    return null;
  }

  const lower = text.toLowerCase();
  const skills = [
    "react",
    "node",
    "python",
    "fastapi",
    "aws",
    "docker",
    "kubernetes",
    "sql",
    "machine learning",
    "leadership"
  ].filter((skill) => lower.includes(skill));

  const projects = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 12 && /project|built|designed|developed|launched/i.test(line))
    .slice(0, 4);

  const achievements = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 16 && /\d+%|\$\d+|\d+x|improved|reduced|increased|optimized|scaled/i.test(line))
    .slice(0, 4);

  const experience = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 8 && /engineer|developer|manager|scientist|analyst|intern/i.test(line))
    .slice(0, 4);

  const keywords = [
    "scalability",
    "performance",
    "microservices",
    "api",
    "leadership",
    "testing",
    "security",
    "ci/cd"
  ].filter((word) => lower.includes(word));

  return {
    skills,
    projects,
    achievements,
    experience,
    keywords,
    raw_text: text.slice(0, 2000),
    summary: summarizeResume(text)
  };
}

function formatParsedResumeSummary(parsed) {
  if (!parsed) {
    return "";
  }

  if (parsed.summary) {
    return parsed.summary;
  }

  const bullets = [];
  if (parsed.skills?.length) {
    bullets.push(`- Skills: ${parsed.skills.slice(0, 6).join(", ")}`);
  }
  if (parsed.projects?.length) {
    bullets.push(`- Projects: ${parsed.projects.slice(0, 3).join(" | ")}`);
  }
  if (parsed.achievements?.length) {
    bullets.push(`- Achievements: ${parsed.achievements.slice(0, 2).join(" | ")}`);
  }
  if (parsed.experience?.length) {
    bullets.push(`- Experience: ${parsed.experience.slice(0, 2).join(" | ")}`);
  }
  if (parsed.raw_text) {
    bullets.push(`- Snapshot: ${parsed.raw_text.slice(0, 180)}`);
  }
  return bullets.join("\n");
}

function normalizePersona(persona, fallback) {
  if (persona && typeof persona === "object") {
    return persona;
  }

  return fallback;
}

function isRateLimitedOrUnavailable(error) {
  return error?.status === 429 || error?.providerReason === "github_models_rate_limited" || error?.status === 503;
}

function wait(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export default function InterviewUI() {
  const persistedStateRef = useRef(loadStoredJson(STORAGE_KEY, {}));
  const persistedHistoryRef = useRef(loadStoredJson(HISTORY_KEY, []));
  const persistedState = persistedStateRef.current;

  const [role, setRole] = useState(persistedState.role || "SWE");
  const [questionType, setQuestionType] = useState(persistedState.questionType || "Behavioral");
  const [interviewMode, setInterviewMode] = useState(persistedState.interviewMode || "Standard");
  const [interviewer, setInterviewer] = useState(persistedState.interviewer || "Friendly HR");
  const [resumeText, setResumeText] = useState(persistedState.resumeText || "");
  const [resumeSummary, setResumeSummary] = useState(persistedState.resumeSummary || "");
  const [resumeData, setResumeData] = useState(persistedState.resumeData || null);
  const [messages, setMessages] = useState(persistedState.messages || []);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState(
    persistedState.messages?.length
      ? "Restored saved transcript. Start a new interview to continue live."
      : "Ready to start your interview."
  );
  const [loading, setLoading] = useState(false);
  const [isVoiceRecording, setIsVoiceRecording] = useState(false);
  const [started, setStarted] = useState(false);
  const [currentPanel, setCurrentPanel] = useState(persistedState.currentPanel || 0);
  const [scores, setScores] = useState(persistedState.scores || []);
  const [fileName, setFileName] = useState(persistedState.fileName || "");
  const [panelRoster, setPanelRoster] = useState(persistedState.panelRoster || []);
  const [voiceMode, setVoiceMode] = useState(persistedState.voiceMode || "Text Only");
  const [sessionId, setSessionId] = useState(null);
  const [recentSessions, setRecentSessions] = useState(
    Array.isArray(persistedHistoryRef.current) ? persistedHistoryRef.current : []
  );
  const autoStopVoiceTimerRef = useRef(null);
  const chatEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const { startModelInterview, continueModelInterview } = useModelInference();

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        role,
        questionType,
        interviewMode,
        interviewer,
        resumeText,
        resumeSummary,
        resumeData,
        messages,
        scores,
        fileName,
        currentPanel,
        panelRoster,
        voiceMode
      })
    );
  }, [
    role,
    questionType,
    interviewMode,
    interviewer,
    resumeText,
    resumeSummary,
    resumeData,
    messages,
    scores,
    fileName,
    currentPanel,
    panelRoster,
    voiceMode
  ]);

  useEffect(() => {
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(recentSessions));
  }, [recentSessions]);

  const interviewerOptions = INTERVIEWERS[interviewMode] || INTERVIEWERS.Standard;

  const voiceInputEnabled = voiceMode === "Speak Answer" || voiceMode === "Both (Hear + Speak)";
  const voiceOutputEnabled = voiceMode === "Hear Interviewer" || voiceMode === "Both (Hear + Speak)";

  const retryModelCall = async (runner, {
    attempts = 3,
    baseDelayMs = 900,
    statusPrefix = "AI model busy"
  } = {}) => {
    let lastError;

    for (let attempt = 0; attempt < attempts; attempt += 1) {
      try {
        return await runner();
      } catch (error) {
        lastError = error;

        if (!isRateLimitedOrUnavailable(error) || attempt === attempts - 1) {
          throw error;
        }

        const delay = baseDelayMs * (attempt + 1);
        setStatus(`${statusPrefix}. Retrying (${attempt + 1}/${attempts - 1})...`);
        await wait(delay);
      }
    }

    throw lastError;
  };

  const resetVoiceAutoStopTimer = () => {
    if (autoStopVoiceTimerRef.current) {
      window.clearTimeout(autoStopVoiceTimerRef.current);
      autoStopVoiceTimerRef.current = null;
    }

    autoStopVoiceTimerRef.current = window.setTimeout(async () => {
      try {
        await audio.stop();
      } catch (error) {
        setIsVoiceRecording(false);
        setStatus("Voice capture timed out. Please try again.");
      }
    }, VOICE_AUTO_STOP_MS);
  };

  async function submitAnswer(userText) {
    if (!userText || loading || !sessionId) {
      return;
    }

    const userMessage = { role: "user", text: userText };
    const pendingMessages = [...messages, userMessage];

    setInput("");
    setMessages(pendingMessages);
    setLoading(true);
    setStatus("Interviewer is responding...");

    try {
      const userTurns = pendingMessages.filter((message) => message.role === "user").length;
      const panelIndex = interviewMode === "Panel"
        ? Math.floor(userTurns / 2) % PANEL_PERSONAS.length
        : 0;

      if (interviewMode === "Panel") {
        setCurrentPanel(panelIndex);
      }

      const {
        evaluationData: evalData,
        feedbackData: feedback,
        questionData
      } = await retryModelCall(
        () => continueModelInterview({
          sessionId,
          role,
          questionType,
          mode: toBackendMode(interviewMode),
          interviewer,
          resumeSummary,
          resumeData,
          messages: pendingMessages,
          candidateAnswer: userText,
          maxQuestionWords: interviewMode === "Speed Round" ? 22 : 35
        }),
        { attempts: 1, baseDelayMs: 0, statusPrefix: "Model is temporarily busy" }
      );

      const scoreOverall = evalData?.scores?.overall;
      if (typeof scoreOverall === "number") {
        setScores((previous) => [...previous, scoreOverall]);
      }

      setPanelRoster(questionData.panel_members || panelRoster);

      const assistantPersona = normalizePersona(
        questionData.persona,
        buildAssistantPersona(
          interviewMode,
          interviewer,
          panelIndex,
          interviewer
        )
      );

      if (voiceOutputEnabled) {
        const ok = await audio.speak(questionData.question);
        if (!ok) {
          setStatus("Could not auto-play interviewer voice. Click Play on the message.");
        }
      }

      const feedbackMessage = {
        role: "feedback",
        text: feedback.feedback,
        evaluation: {
          score: evalData?.scores?.overall ?? null,
          semantic: (evalData?.scores?.technical_depth ?? 0) / 10,
          clarity: (evalData?.scores?.clarity ?? 0) / 10,
          vagueness: 1 - Math.min(1, Math.max(0, (evalData?.scores?.relevance ?? 0) / 10)),
          star: (evalData?.scores?.structure_star ?? 0) / 10,
          confidence: evalData?.confidence,
          uncertainty_flags: evalData?.uncertainty_flags || []
        }
      };

      const nextQuestionMessage = {
        role: "assistant",
        text: questionData.question,
        persona: assistantPersona,
        agent: assistantPersona?.name || interviewer,
        questionType
      };

      setMessages([
        ...pendingMessages,
        feedbackMessage,
        nextQuestionMessage
      ]);

      setStatus("Waiting for your response...");
    } catch (error) {
      const isRateLimit = error.status === 429 || error.providerReason === "github_models_rate_limited";
      const isUnavailable = error.status === 503;
      const isTimeout = error.status === 408 || /timed out|timeout/i.test(error.message || "");
      if (isRateLimit) {
        setStatus("Model is still busy after retries. Please try once more.");
      } else if (isTimeout) {
        setStatus("Model is taking too long to respond. Please send again.");
      } else if (isUnavailable) {
        setStatus("Model is currently unavailable after retries. Please try again shortly.");
      } else {
        setStatus(`Error: ${error.message || "Check the backend logs."}`);
      }
    } finally {
      setLoading(false);
    }
  }

  const audio = useAudio((data) => {
    if (data?.error) {
      setIsVoiceRecording(false);
      setStatus(`Voice input error: ${data.error}. Please allow microphone access and retry.`);
      return;
    }

    if (data?.listening) {
      setStatus(data.fallback ? "Recording via fallback..." : "Listening...");
      if (isVoiceRecording) {
        resetVoiceAutoStopTimer();
      }
      return;
    }

    if (data?.interim) {
      if (data.transcribed_text) {
        setInput(data.transcribed_text);
      }
      setStatus("Listening...");
      if (isVoiceRecording) {
        resetVoiceAutoStopTimer();
      }
      return;
    }

    if (data?.done) {
      setIsVoiceRecording(false);
      if (autoStopVoiceTimerRef.current) {
        window.clearTimeout(autoStopVoiceTimerRef.current);
        autoStopVoiceTimerRef.current = null;
      }
    }

    if (data?.transcribed_text) {
      const spoken = data.transcribed_text.trim();
      setInput(spoken);

      if (voiceMode === "Both (Hear + Speak)" && spoken && started && sessionId && !loading) {
        setStatus("Voice captured. Sending automatically...");
        submitAnswer(spoken);
        return;
      }

      setStatus("Voice captured. Review the text and send it.");
      return;
    }

    setStatus("Voice capture finished, but no transcript was returned.");
  });

  const archiveCurrentSession = () => {
    if (!messages.length) {
      return;
    }

    const snapshot = {
      id: `session-${Date.now()}`,
      savedAt: new Date().toISOString(),
      role,
      questionType,
      interviewMode,
      interviewer,
      voiceMode,
      resumeText,
      resumeSummary,
      resumeData,
      fileName,
      messages,
      scores,
      panelRoster
    };

    setRecentSessions((previous) => [snapshot, ...previous].slice(0, 6));
  };

  const restoreSnapshot = (snapshot) => {
    setRole(snapshot.role || "SWE");
    setQuestionType(snapshot.questionType || "Behavioral");
    setInterviewMode(snapshot.interviewMode || "Standard");
    setInterviewer(snapshot.interviewer || INTERVIEWERS.Standard[0]);
    setResumeText(snapshot.resumeText || "");
    setResumeSummary(snapshot.resumeSummary || "");
    setResumeData(snapshot.resumeData || null);
    setFileName(snapshot.fileName || "");
    setMessages(snapshot.messages || []);
    setScores(snapshot.scores || []);
    setPanelRoster(snapshot.panelRoster || []);
    setVoiceMode(snapshot.voiceMode || "Text Only");
    setStarted(false);
    setSessionId(null);
    setStatus("Saved transcript restored. Start a new interview to continue live.");
  };

  const handleStartInterview = async () => {
    archiveCurrentSession();
    setLoading(true);
    setMessages([]);
    setScores([]);
    setStarted(true);
    setCurrentPanel(0);
    setPanelRoster([]);
    setStatus("Interview in progress...");

    const derivedResumeData = resumeData || buildResumeDataFromText(resumeText);
    const summary = derivedResumeData?.summary || summarizeResume(resumeText);
    setResumeData(derivedResumeData);
    setResumeSummary(summary);

    try {
      const { sessionId: newSessionId, questionData: data } = await retryModelCall(
        () => startModelInterview({
          role,
          questionType,
          mode: toBackendMode(interviewMode),
          interviewer,
          resumeSummary: summary,
          resumeData: derivedResumeData,
          maxQuestionWords: interviewMode === "Speed Round" ? 22 : 35
        }),
        { attempts: 1, baseDelayMs: 0, statusPrefix: "Model is warming up" }
      );
      setSessionId(newSessionId);

      setPanelRoster(data.panel_members || []);

      const firstPersona = normalizePersona(
        data.persona,
        buildAssistantPersona(interviewMode, interviewer, 0, data.agent)
      );

      setMessages([
        {
          role: "assistant",
          text: data.question,
          persona: firstPersona,
          agent: firstPersona?.name || interviewer,
          questionType
        }
      ]);

      if (voiceOutputEnabled) {
        const ok = await audio.speak(data.question);
        if (!ok) {
          setStatus("Auto voice playback was blocked. Use Play on the question card.");
        }
      }

      setStatus("Waiting for your response...");
    } catch (error) {
      setStarted(false);
      const isRateLimit = error.status === 429 || error.providerReason === "github_models_rate_limited";
      const isUnavailable = error.status === 503;
      const isTimeout = error.status === 408 || /timed out|timeout/i.test(error.message || "");
      if (isRateLimit) {
        setStatus("Model is still busy after retries. Please click Start again.");
      } else if (isTimeout) {
        setStatus("Generating first question is taking too long. Please click Start again.");
      } else if (isUnavailable) {
        setStatus("Model unavailable after retries. Please start again in a moment.");
      } else {
        setStatus(`Error starting interview: ${error.message || "Check that the backend is running on port 8000."}`);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    if (!input.trim()) {
      return;
    }
    await submitAnswer(input.trim());
  };

  const handleFileUpload = (event) => {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    setFileName(file.name);

    if (file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")) {
      setStatus("Parsing PDF resume...");
      parseResumeFile(file)
        .then((parsed) => {
          setResumeData(parsed);
          setResumeText(parsed.raw_text || "");
          setResumeSummary(formatParsedResumeSummary(parsed));
          setStatus("PDF resume parsed successfully.");
        })
        .catch((error) => {
          setStatus(`Resume parsing failed: ${error.message}`);
        });
      return;
    }

    const reader = new FileReader();
    reader.onload = (loadEvent) => {
      const text = typeof loadEvent.target?.result === "string" ? loadEvent.target.result : "";
      setResumeData(null);
      setResumeText(text);
      setResumeSummary(summarizeResume(text));
      setStatus("Resume text loaded.");
    };
    reader.readAsText(file);
  };

  const handleVoice = async () => {
    setStatus("Speak clicked. Preparing microphone...");

    if (!voiceInputEnabled) {
      setVoiceMode("Both (Hear + Speak)");
      setStatus("Voice mode switched to Both. Click Speak again to start.");
      return;
    }

    if (!audio.canUseSpeechInput) {
      setStatus("Browser speech API unavailable. Using upload-based voice transcription fallback...");
    }

    try {
      if (!isVoiceRecording) {
        setStatus("Listening... speak now.");
        setIsVoiceRecording(true);
        await audio.start();
        resetVoiceAutoStopTimer();
        return;
      }

      setStatus("Stopping capture...");
      await audio.stop();
      if (autoStopVoiceTimerRef.current) {
        window.clearTimeout(autoStopVoiceTimerRef.current);
        autoStopVoiceTimerRef.current = null;
      }
      setIsVoiceRecording(false);
    } catch (error) {
      if (autoStopVoiceTimerRef.current) {
        window.clearTimeout(autoStopVoiceTimerRef.current);
        autoStopVoiceTimerRef.current = null;
      }
      setIsVoiceRecording(false);
      setStatus("Voice recording failed. Check microphone permissions.");
    }
  };

  const averageScore = scores.length > 0
    ? (scores.reduce((total, value) => total + value, 0) / scores.length).toFixed(1)
    : null;

  const playAssistantMessage = async (text) => {
    const questionText = (text || "").trim();
    if (!questionText) {
      setStatus("No question text available to play.");
      return;
    }

    const ok = await audio.speak(questionText);
    if (!ok) {
      setStatus("Voice playback unavailable. Check browser autoplay/sound settings.");
      return;
    }

    setStatus("Playing interviewer question...");
  };

  return (
    <div
      style={{
        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
        background: "#111214",
        color: "#e2e8f0",
        minHeight: "100vh",
        padding: "24px",
        boxSizing: "border-box"
      }}
    >
      <div style={{ marginBottom: 24 }}>
        <h1
          style={{
            margin: 0,
            fontSize: 22,
            fontWeight: 700,
            color: "#f8fafc",
            letterSpacing: "-0.5px"
          }}
        >
          AI Interview Simulator
        </h1>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: "#94a3b8" }}>
          Role-based mock interview with resume context, panel personas, and answer scoring.
        </p>
      </div>

      <div
        style={{
          marginBottom: 16,
          padding: "10px 12px",
          borderRadius: 8,
          border: "1px solid #334155",
          background: "#0f172a",
          color: "#cbd5e1",
          fontSize: 12
        }}
      >
        Status: {status}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 16,
          marginBottom: 20
        }}
      >
        {[
          { label: "Role", value: role, setter: setRole, options: ROLES },
          { label: "Question Type", value: questionType, setter: setQuestionType, options: QUESTION_TYPES },
          {
            label: "Interview Mode",
            value: interviewMode,
            setter: (value) => {
              setInterviewMode(value);
              setInterviewer(INTERVIEWERS[value][0]);
              setCurrentPanel(0);
            },
            options: INTERVIEW_MODES
          },
          {
            label: interviewMode === "Panel" ? "Panel Style" : "Interviewer",
            value: interviewer,
            setter: setInterviewer,
            options: interviewerOptions
          },
          {
            label: "Voice Mode",
            value: voiceMode,
            setter: setVoiceMode,
            options: VOICE_MODES
          }
        ].map(({ label, value, setter, options }) => (
          <div
            key={label}
            style={{
              background: "#1a1d23",
              border: "1px solid #2d3748",
              borderRadius: 8,
              padding: "12px 14px"
            }}
          >
            <div
              style={{
                fontSize: 11,
                color: "#64748b",
                marginBottom: 6,
                textTransform: "uppercase",
                letterSpacing: "0.08em"
              }}
            >
              {label}
            </div>
            <select
              value={value}
              onChange={(event) => setter(event.target.value)}
              style={{
                width: "100%",
                background: "transparent",
                border: "none",
                color: "#e2e8f0",
                fontSize: 13,
                cursor: "pointer",
                outline: "none",
                fontFamily: "inherit"
              }}
            >
              {options.map((option) => (
                <option key={option} value={option} style={{ background: "#1a1d23" }}>
                  {option}
                </option>
              ))}
            </select>
          </div>
        ))}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
          gap: 16,
          marginBottom: 20
        }}
      >
        <div
          style={{
            background: "#1a1d23",
            border: "1px solid #2d3748",
            borderRadius: 8,
            overflow: "hidden"
          }}
        >
          <div
            style={{
              padding: "10px 14px",
              borderBottom: "1px solid #2d3748",
              fontSize: 12,
              color: "#94a3b8"
            }}
          >
            Upload Resume PDF / Text
          </div>
          <div
            style={{
              padding: 20,
              textAlign: "center",
              cursor: "pointer",
              minHeight: 120,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center"
            }}
            onClick={() => fileInputRef.current?.click()}
          >
            <div style={{ fontSize: 13, color: "#64748b" }}>{fileName || "Drop file here"}</div>
            <div style={{ fontSize: 11, color: "#475569", marginTop: 4 }}>or click to upload</div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,.md,.pdf"
              style={{ display: "none" }}
              onChange={handleFileUpload}
            />
          </div>
        </div>

        <div
          style={{
            background: "#1a1d23",
            border: "1px solid #2d3748",
            borderRadius: 8,
            overflow: "hidden"
          }}
        >
          <div
            style={{
              padding: "10px 14px",
              borderBottom: "1px solid #2d3748",
              fontSize: 12,
              color: "#94a3b8"
            }}
          >
            Or paste resume text
          </div>
          <textarea
            value={resumeText}
            onChange={(event) => {
              setResumeText(event.target.value);
              setResumeData(null);
            }}
            placeholder="Paste your resume content here..."
            style={{
              width: "100%",
              height: 120,
              background: "transparent",
              border: "none",
              color: "#cbd5e1",
              fontSize: 12,
              padding: "12px 14px",
              resize: "none",
              outline: "none",
              fontFamily: "inherit",
              boxSizing: "border-box"
            }}
          />
        </div>
      </div>

      <button
        onClick={handleStartInterview}
        disabled={loading}
        style={{
          width: "100%",
          padding: "14px",
          marginBottom: 20,
          background: loading ? "#1e293b" : "#1e3a5f",
          border: `1px solid ${loading ? "#334155" : "#2563eb"}`,
          borderRadius: 8,
          color: loading ? "#475569" : "#93c5fd",
          fontSize: 14,
          fontWeight: 600,
          cursor: loading ? "not-allowed" : "pointer",
          fontFamily: "inherit",
          letterSpacing: "0.05em",
          transition: "all 0.2s"
        }}
      >
        {loading && !started ? "Initializing..." : "Start Interview"}
      </button>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
          gap: 16
        }}
      >
        <div
          style={{
            background: "#1a1d23",
            border: "1px solid #2d3748",
            borderRadius: 8,
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
            minHeight: 520
          }}
        >
          <div
            style={{
              padding: "10px 14px",
              borderBottom: "1px solid #2d3748",
              fontSize: 12,
              color: "#94a3b8",
              display: "flex",
              alignItems: "center",
              gap: 6
            }}
          >
            Interview
            {averageScore && (
              <span
                style={{
                  marginLeft: "auto",
                  fontSize: 12,
                  color: scoreColor(parseFloat(averageScore)),
                  fontWeight: 700
                }}
              >
                Avg Score: {averageScore}/10
              </span>
            )}
          </div>

          <div
            style={{
              flex: 1,
              overflowY: "auto",
              padding: 16,
              display: "flex",
              flexDirection: "column",
              gap: 12,
              maxHeight: 420
            }}
          >
            {messages.length === 0 && (
              <div style={{ color: "#475569", fontSize: 12, textAlign: "center", marginTop: 40 }}>
                Configure your settings above and click Start Interview.
              </div>
            )}

            {messages.map((message, index) => {
              // ── Feedback card ──────────────────────────────────────────
              if (message.role === "feedback") {
                const fbScore = typeof message.evaluation?.score === "number"
                  ? Number(message.evaluation.score.toFixed(1))
                  : null;
                return (
                  <div
                    key={`feedback-${index}`}
                    style={{
                      alignSelf: "stretch",
                        background: feedbackTheme(fbScore).bg,
                        border: `1px solid ${feedbackTheme(fbScore).border}`,
                        borderLeft: `3px solid ${feedbackTheme(fbScore).accent}`,
                      borderRadius: 8,
                      padding: "10px 14px"
                    }}
                  >
                    <div
                      style={{
                        fontSize: 10,
                          color: feedbackTheme(fbScore).accent,
                        textTransform: "uppercase",
                        letterSpacing: "0.1em",
                        marginBottom: 6,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between"
                      }}
                    >
                        <span>{feedbackTheme(fbScore).label}</span>
                      {fbScore !== null && (
                        <span
                          style={{
                            fontSize: 12,
                            color: scoreColor(fbScore),
                            fontWeight: 700,
                            padding: "2px 8px",
                            background: "#0f172a",
                            borderRadius: 4,
                            border: `1px solid ${scoreColor(fbScore)}44`
                          }}
                        >
                          {fbScore}/10
                        </span>
                      )}
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                          color: feedbackTheme(fbScore).text,
                        lineHeight: 1.65,
                        whiteSpace: "pre-wrap"
                      }}
                    >
                      {message.text}
                    </div>
                  </div>
                );
              }

              // ── User / Assistant bubbles ───────────────────────────────
              return (
                <div
                  key={`${message.role}-${index}`}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: message.role === "user" ? "flex-end" : "flex-start"
                  }}
                >
                  {message.persona && message.role === "assistant" && (
                    <div
                      style={{
                        fontSize: 11,
                        color: "#64748b",
                        marginBottom: 4,
                        display: "flex",
                        alignItems: "center",
                        gap: 4
                      }}
                    >
                      <span style={{ color: "#7c8a9e" }}>{message.persona.name}</span>
                      <span>{message.persona.role}</span>
                    </div>
                  )}

                  <div
                    style={{
                      maxWidth: "85%",
                      padding: "10px 14px",
                      borderRadius: message.role === "user"
                        ? "12px 12px 2px 12px"
                        : "12px 12px 12px 2px",
                      background: message.role === "user" ? "#1e3a5f" : "#1e2433",
                      border: `1px solid ${message.role === "user" ? "#2563eb33" : "#2d3748"}`,
                      fontSize: 13,
                      lineHeight: 1.6,
                      color: message.role === "user" ? "#bfdbfe" : "#cbd5e1",
                      whiteSpace: "pre-wrap"
                    }}
                  >
                    {message.text}
                    {message.role === "assistant" && (
                      <div style={{ marginTop: 8 }}>
                        <button
                          onClick={() => playAssistantMessage(message.text)}
                          style={{
                            padding: "4px 8px",
                            background: "#0f172a",
                            border: "1px solid #334155",
                            borderRadius: 4,
                            color: "#93c5fd",
                            fontSize: 11,
                            cursor: "pointer",
                            fontFamily: "inherit"
                          }}
                        >
                          Play
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {loading && started && <div style={{ color: "#475569", fontSize: 12 }}>Thinking...</div>}
            <div ref={chatEndRef} />
          </div>

          {started && (
            <div
              style={{
                padding: "12px 14px",
                borderTop: "1px solid #2d3748",
                display: "flex",
                gap: 8,
                alignItems: "flex-end"
              }}
            >
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="Type your answer... Enter to send, Shift+Enter for newline"
                rows={2}
                style={{
                  flex: 1,
                  background: "#0f172a",
                  border: "1px solid #334155",
                  borderRadius: 6,
                  color: "#e2e8f0",
                  fontSize: 12,
                  padding: "8px 10px",
                  resize: "none",
                  outline: "none",
                  fontFamily: "inherit"
                }}
              />
              <button
                onClick={handleVoice}
                disabled={false}
                title={voiceInputEnabled ? "Start/stop voice input" : "Enable Speak Answer or Both mode to use voice input"}
                style={{
                  padding: "8px 12px",
                  background: "#422006",
                  border: "1px solid #ea580c",
                  borderRadius: 6,
                  color: "#fdba74",
                  cursor: "pointer",
                  fontSize: 12,
                  fontFamily: "inherit",
                  opacity: 1
                }}
              >
                {isVoiceRecording ? "Stop" : "Speak"}
              </button>
              <button
                onClick={handleSend}
                disabled={loading || !input.trim()}
                style={{
                  padding: "8px 16px",
                  background: "#1e3a5f",
                  border: "1px solid #2563eb",
                  borderRadius: 6,
                  color: "#93c5fd",
                  cursor: loading || !input.trim() ? "not-allowed" : "pointer",
                  fontSize: 13,
                  fontFamily: "inherit",
                  fontWeight: 600,
                  opacity: loading || !input.trim() ? 0.4 : 1
                }}
              >
                Send
              </button>
            </div>
          )}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div
            style={{
              background: "#1a1d23",
              border: "1px solid #2d3748",
              borderRadius: 8,
              overflow: "hidden"
            }}
          >
            <div
              style={{
                padding: "10px 14px",
                borderBottom: "1px solid #2d3748",
                fontSize: 12,
                color: "#94a3b8"
              }}
            >
              Parsed Resume Summary
            </div>
            <div
              style={{
                padding: 14,
                fontSize: 12,
                color: "#94a3b8",
                lineHeight: 1.7,
                whiteSpace: "pre-wrap",
                minHeight: 120
              }}
            >
              {resumeSummary || (
                <span style={{ color: "#475569" }}>
                  Resume summary will appear here after you start the interview with resume text provided.
                </span>
              )}
            </div>
          </div>

          {recentSessions.length > 0 && (
            <div
              style={{
                background: "#1a1d23",
                border: "1px solid #2d3748",
                borderRadius: 8,
                overflow: "hidden"
              }}
            >
              <div
                style={{
                  padding: "10px 14px",
                  borderBottom: "1px solid #2d3748",
                  fontSize: 12,
                  color: "#94a3b8"
                }}
              >
                Saved Transcript History
              </div>
              <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 10 }}>
                {recentSessions.map((snapshot) => (
                  <div
                    key={snapshot.id}
                    style={{
                      border: "1px solid #2d3748",
                      borderRadius: 6,
                      padding: 10,
                      background: "#111827"
                    }}
                  >
                    <div style={{ fontSize: 12, color: "#e2e8f0", marginBottom: 4 }}>
                      {snapshot.role} · {snapshot.interviewMode} · {snapshot.questionType}
                    </div>
                    <div style={{ fontSize: 11, color: "#64748b", marginBottom: 8 }}>
                      {new Date(snapshot.savedAt).toLocaleString()}
                    </div>
                    <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 8 }}>
                      {(snapshot.messages?.[0]?.text || "No preview available.").slice(0, 100)}
                    </div>
                    <button
                      onClick={() => restoreSnapshot(snapshot)}
                      style={{
                        padding: "6px 10px",
                        background: "#1e3a5f",
                        border: "1px solid #2563eb",
                        borderRadius: 6,
                        color: "#93c5fd",
                        cursor: "pointer",
                        fontSize: 11,
                        fontFamily: "inherit"
                      }}
                    >
                      Load Snapshot
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {panelRoster.length > 0 && interviewMode === "Panel" && (
            <div
              style={{
                background: "#1a1d23",
                border: "1px solid #2d3748",
                borderRadius: 8,
                overflow: "hidden"
              }}
            >
              <div
                style={{
                  padding: "10px 14px",
                  borderBottom: "1px solid #2d3748",
                  fontSize: 12,
                  color: "#94a3b8"
                }}
              >
                Active Panel
              </div>
              <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 8 }}>
                {panelRoster.map((member) => (
                  <div
                    key={`${member.name}-${member.role}`}
                    style={{
                      border: "1px solid #2d3748",
                      borderRadius: 6,
                      padding: 10,
                      background: "#111827"
                    }}
                  >
                    <div style={{ fontSize: 12, color: "#e2e8f0" }}>
                      {member.name} · {member.role}
                    </div>
                    <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4 }}>
                      {member.focus}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {scores.length > 0 && (
            <div
              style={{
                background: "#1a1d23",
                border: "1px solid #2d3748",
                borderRadius: 8,
                overflow: "hidden"
              }}
            >
              <div
                style={{
                  padding: "10px 14px",
                  borderBottom: "1px solid #2d3748",
                  fontSize: 12,
                  color: "#94a3b8"
                }}
              >
                Answer Scores
              </div>
              <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 8 }}>
                {scores.map((score, index) => (
                  <div key={`${score}-${index}`} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: 11, color: "#64748b", minWidth: 60 }}>Q{index + 1}</span>
                    <div style={{ flex: 1, height: 6, background: "#0f172a", borderRadius: 3, overflow: "hidden" }}>
                      <div
                        style={{
                          width: `${Math.max(0, Math.min(score, 10)) * 10}%`,
                          height: "100%",
                          background: scoreColor(score),
                          borderRadius: 3,
                          transition: "width 0.5s ease"
                        }}
                      />
                    </div>
                    <span
                      style={{
                        fontSize: 12,
                        color: scoreColor(score),
                        fontWeight: 700,
                        minWidth: 42,
                        textAlign: "right"
                      }}
                    >
                      {Number(score).toFixed(1)}/10
                    </span>
                  </div>
                ))}

                <div
                  style={{
                    marginTop: 4,
                    paddingTop: 8,
                    borderTop: "1px solid #2d3748",
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: 12
                  }}
                >
                  <span style={{ color: "#64748b" }}>Average</span>
                  <span style={{ color: scoreColor(parseFloat(averageScore)), fontWeight: 700 }}>
                    {averageScore}/10
                  </span>
                </div>
              </div>
            </div>
          )}

          <div
            style={{
              background: "#1a1d23",
              border: "1px solid #2d3748",
              borderRadius: 8,
              padding: "12px 14px"
            }}
          >
            <div
              style={{
                fontSize: 11,
                color: "#64748b",
                marginBottom: 4,
                textTransform: "uppercase",
                letterSpacing: "0.08em"
              }}
            >
              Status
            </div>
            <div
              style={{
                fontSize: 12,
                color: loading ? "#facc15" : "#4ade80",
                display: "flex",
                alignItems: "center",
                gap: 6
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: loading ? "#facc15" : "#4ade80",
                  display: "inline-block"
                }}
              />
              {status}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}