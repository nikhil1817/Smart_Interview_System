import pyttsx3
import uuid
import os

def text_to_audio(text: str):
    """
    Convert text to audio file using pyttsx3 (offline TTS)
    """
    try:
        engine = pyttsx3.init()
        filename = f"audio_{uuid.uuid4()}.wav"

        # Configure voice settings
        voices = engine.getProperty('voices')
        if voices:
            engine.setProperty('voice', voices[0].id)  # Use first available voice

        engine.save_to_file(text, filename)
        engine.runAndWait()

        return filename

    except Exception as e:
        print(f"TTS error: {e}")
        # Return a dummy filename for now
        return "dummy_audio.wav"