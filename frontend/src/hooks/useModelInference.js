import {
  evaluateModelAnswer,
  generateModelFeedback,
  generateModelQuestion
} from "../services/apiService";

function createLocalSessionId() {
  if (typeof window !== "undefined" && window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }
  return `session-${Date.now()}-${Math.floor(Math.random() * 100000)}`;
}

function toConversationContext(messages) {
  return messages
    .map((message) => {
      if (message.role === "assistant" || message.role === "user") {
        return { speaker: message.role, text: message.text };
      }
      return null;
    })
    .filter(Boolean);
}

export function useModelInference() {
  const startModelInterview = async ({
    role,
    questionType,
    mode,
    interviewer,
    resumeSummary,
    resumeData,
    maxQuestionWords
  }) => {
    const sessionId = createLocalSessionId();

    const questionData = await generateModelQuestion({
      session_id: sessionId,
      role_target: role,
      question_type: questionType,
      mode,
      interviewer_persona: interviewer,
      resume_summary: resumeSummary,
      resume_data: resumeData || null,
      conversation_context: [],
      candidate_answer: "",
      constraints: {
        max_question_words: maxQuestionWords,
        difficulty: "medium"
      }
    });

    return {
      sessionId,
      questionData
    };
  };

  const continueModelInterview = async ({
    sessionId,
    role,
    questionType,
    mode,
    interviewer,
    resumeSummary,
    resumeData,
    messages,
    candidateAnswer,
    maxQuestionWords
  }) => {
    const context = toConversationContext(messages);
    const lastQuestion = [...messages]
      .reverse()
      .find((message) => message.role === "assistant")?.text || "";

    const evaluationPromise = evaluateModelAnswer({
      session_id: sessionId,
      role_target: role,
      question_type: questionType,
      mode,
      current_question: lastQuestion,
      candidate_answer: candidateAnswer,
      conversation_context: context
    });

    const questionPromise = generateModelQuestion({
      session_id: sessionId,
      role_target: role,
      question_type: questionType,
      mode,
      interviewer_persona: interviewer,
      resume_summary: resumeSummary,
      resume_data: resumeData || null,
      conversation_context: context,
      candidate_answer: candidateAnswer,
      constraints: {
        max_question_words: maxQuestionWords,
        difficulty: "medium"
      }
    });

    const [evaluationData, questionData] = await Promise.all([
      evaluationPromise,
      questionPromise
    ]);

    const feedbackData = await generateModelFeedback({
      session_id: sessionId,
      current_question: lastQuestion,
      candidate_answer: candidateAnswer,
      scores: evaluationData.scores,
      role_target: role,
      question_type: questionType
    });

    return {
      evaluationData,
      feedbackData,
      questionData
    };
  };

  return {
    startModelInterview,
    continueModelInterview
  };
}
