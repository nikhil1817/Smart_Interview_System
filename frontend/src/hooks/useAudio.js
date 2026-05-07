import { useRef } from "react";
import { startRecording, stopRecording, sendAudio } from "../services/audioService";

export function useAudio(onResult) {
  const recognitionRef = useRef(null);
  const transcriptRef = useRef("");
  const resolveStopRef = useRef(null);
  const rejectStopRef = useRef(null);
  const isListeningRef = useRef(false);
  const selectedVoiceRef = useRef(null);
  const fallbackRecordingRef = useRef(false);

  const SpeechRecognition =
    typeof window !== "undefined"
      ? window.SpeechRecognition || window.webkitSpeechRecognition
      : null;

  const canUseSpeechInput = Boolean(SpeechRecognition);
  const canUseSpeechOutput = typeof window !== "undefined" && "speechSynthesis" in window;

  // Ordered list of high-quality named voices available in Chrome/Safari/Edge.
  // macOS: Samantha, Alex, Karen, Moira. Windows: Zira, David. Edge: Aria, Guy.
  const PREMIUM_VOICE_NAMES = [
    "Samantha",         // macOS — neural, clear, natural
    "Alex",             // macOS — classic high-quality
    "Karen",            // macOS Australian, very clear
    "Daniel",           // macOS UK
    "Moira",            // macOS Irish
    "Aria",             // Microsoft Edge neural
    "Guy",              // Microsoft Edge neural
    "Jenny",            // Microsoft Edge neural
    "Zira",             // Windows
    "Google UK English Female",
    "Google UK English Male",
  ];

  const pickVoice = () => {
    if (!canUseSpeechOutput) {
      return null;
    }

    const voices = window.speechSynthesis.getVoices();
    if (!voices.length) {
      return null;
    }

    // Try premium voices in priority order first.
    for (const name of PREMIUM_VOICE_NAMES) {
      const match = voices.find((v) => v.name === name);
      if (match) return match;
    }

    // Fall back to any en-US, then any English, then first available.
    return (
      voices.find((v) => /en-US|en_US/i.test(v.lang) && v.localService) ||
      voices.find((v) => /en-US|en_US/i.test(v.lang)) ||
      voices.find((v) => /^en/i.test(v.lang)) ||
      voices[0]
    );
  };

  const ensureVoiceReady = () => {
    if (!canUseSpeechOutput) {
      return;
    }

    if (!selectedVoiceRef.current) {
      selectedVoiceRef.current = pickVoice();
    }

    if (!selectedVoiceRef.current) {
      window.speechSynthesis.onvoiceschanged = () => {
        selectedVoiceRef.current = pickVoice();
      };
      window.speechSynthesis.getVoices();
    }
  };

  const buildRecognition = () => {
    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    // Keep recognition running across pauses so longer answers are not cut off.
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const chunk = event.results[i][0]?.transcript || "";
        if (event.results[i].isFinal) {
          transcriptRef.current += `${chunk} `;
        } else {
          interim += chunk;
        }
      }
      const merged = `${transcriptRef.current} ${interim}`.trim();
      if (merged) {
        onResult?.({ transcribed_text: merged, interim: true, done: false });
      }
    };

    recognition.onerror = (event) => {
      isListeningRef.current = false;
      const error = new Error(event.error || "speech_recognition_error");
      onResult?.({ error: error.message, done: true, interim: false });
      if (rejectStopRef.current) {
        rejectStopRef.current(error);
        rejectStopRef.current = null;
        resolveStopRef.current = null;
      }
    };

    recognition.onend = () => {
      isListeningRef.current = false;
      const finalText = transcriptRef.current.trim();
      const payload = { transcribed_text: finalText, interim: false, done: true };
      onResult?.(payload);
      if (resolveStopRef.current) {
        resolveStopRef.current(payload);
        resolveStopRef.current = null;
        rejectStopRef.current = null;
      }
    };

    return recognition;
  };

  const start = async () => {
    if (canUseSpeechInput) {
      // Prompt mic permission early to avoid silent recognition failure.
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());

      transcriptRef.current = "";
      if (!recognitionRef.current) {
        recognitionRef.current = buildRecognition();
      }
      recognitionRef.current.start();
      isListeningRef.current = true;
      onResult?.({ listening: true, done: false, interim: false });
      return;
    }

    fallbackRecordingRef.current = true;
    await startRecording();
    onResult?.({ listening: true, done: false, interim: false, fallback: true });
  };

  const stop = async () => {
    if (canUseSpeechInput && recognitionRef.current && isListeningRef.current) {
      return new Promise((resolve, reject) => {
        resolveStopRef.current = resolve;
        rejectStopRef.current = reject;
        recognitionRef.current.stop();
      });
    }

    if (!fallbackRecordingRef.current) {
      return { transcribed_text: "", done: true, interim: false };
    }

    const blob = await stopRecording();
    const data = await sendAudio(blob);
    const finalData = { ...data, interim: false, done: true };
    onResult(finalData);
    fallbackRecordingRef.current = false;
    return finalData;
  };

  const speakViaTTS = async (text) => {
    try {
      const res = await fetch("http://localhost:8000/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) return false;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      return new Promise((resolve) => {
        const audio = new Audio(url);
        audio.onended = () => { URL.revokeObjectURL(url); resolve(true); };
        audio.onerror = () => { URL.revokeObjectURL(url); resolve(false); };
        audio.play().catch(() => resolve(false));
      });
    } catch {
      return false;
    }
  };

  const speak = (text, options = {}) => {
    if (!text?.trim()) return Promise.resolve(false);

    // Try backend TTS first (OpenAI or gTTS), then fall back to browser synthesis.
    return speakViaTTS(text).then((ok) => {
      if (ok) return true;

      // Browser synthesis fallback
      if (!canUseSpeechOutput) return false;

      ensureVoiceReady();

      return new Promise((resolve) => {
        const utterance = new SpeechSynthesisUtterance(text.trim());
        utterance.rate = options.rate ?? 0.95;
        utterance.pitch = options.pitch ?? 1;
        utterance.volume = options.volume ?? 1;

        if (selectedVoiceRef.current) {
          utterance.voice = selectedVoiceRef.current;
          utterance.lang = selectedVoiceRef.current.lang || "en-US";
        } else {
          utterance.lang = "en-US";
        }

        utterance.onend = () => resolve(true);
        utterance.onerror = () => resolve(false);

        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(utterance);
      });
    });
  };

  const stopSpeaking = () => {
    if (!canUseSpeechOutput) {
      return;
    }
    window.speechSynthesis.cancel();
  };

  return {
    start,
    stop,
    speak,
    stopSpeaking,
    canUseSpeechInput,
    canUseSpeechOutput
  };
}
