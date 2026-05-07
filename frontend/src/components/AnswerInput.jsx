import { useState } from "react";
import { Mic, Send } from "lucide-react";

export default function AnswerInput({ onSend, onVoice }) {
  const [text, setText] = useState("");

  return (
    <div className="flex gap-2">
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Type answer..."
        className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      <button
        onClick={() => { onSend(text); setText(""); }}
        className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        <Send size={16} />
      </button>
      <button
        onClick={onVoice}
        className="px-4 py-2 bg-red-500 text-white rounded-md hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-red-500"
      >
        <Mic size={16} />
      </button>
    </div>
  );
}

