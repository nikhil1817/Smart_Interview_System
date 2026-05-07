import { useState } from "react";
import { startInterview, sendAnswer } from "../services/apiService";

export function useInterview() {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [evaluation, setEvaluation] = useState(null);

  const start = async (role, mode) => {
    const data = await startInterview(role, mode);
    setSessionId(data.session_id);
    setMessages([{ sender: data.agent, text: data.question }]);
  };

  const answer = async (text) => {
    const userMsg = { sender: "You", text };
    setMessages((prev) => [...prev, userMsg]);

    const data = await sendAnswer(sessionId, text);

    setMessages((prev) => [
      ...prev,
      { sender: data.agent, text: data.question }
    ]);

    setEvaluation(data.evaluation);
  };

  return { start, answer, messages, evaluation };
}

