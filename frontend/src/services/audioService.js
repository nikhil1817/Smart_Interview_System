const API_BASE = "http://localhost:8000";

let mediaRecorder;
let audioChunks = [];

export async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(stream);

  audioChunks = [];

  mediaRecorder.ondataavailable = (e) => {
    audioChunks.push(e.data);
  };

  mediaRecorder.start();
}

export function stopRecording() {
  return new Promise((resolve) => {
    mediaRecorder.onstop = () => {
      const blob = new Blob(audioChunks, { type: "audio/wav" });
      resolve(blob);
    };

    mediaRecorder.stop();
  });
}

export async function sendAudio(blob) {
  const formData = new FormData();
  formData.append("file", blob, "audio.wav");

  const res = await fetch(`${API_BASE}/api/voice-transcribe`, {
    method: "POST",
    body: formData
  });

  if (!res.ok) {
    throw new Error("Voice transcription request failed");
  }

  return res.json();
}


