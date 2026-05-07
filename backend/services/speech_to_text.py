import speech_recognition as sr

def transcribe_audio(file_path: str):
    """Transcribe an audio file to text using SpeechRecognition."""
    try:
        recognizer = sr.Recognizer()
        with sr.AudioFile(file_path) as source:
            audio = recognizer.record(source)

        # Uses Google's free recognizer endpoint via SpeechRecognition.
        text = recognizer.recognize_google(audio)
        return (text or "").strip()
    except sr.UnknownValueError:
        return ""
    except sr.RequestError:
        return ""
    except Exception as e:
        print(f"Speech recognition error: {e}")
        return ""