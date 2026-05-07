import os
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException
from services.speech_to_text import transcribe_audio
import shutil

router = APIRouter()

@router.post("/voice-transcribe")
async def voice_transcribe(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = temp_file.name

        text = transcribe_audio(temp_path)

        return {
            "transcribed_text": text,
            "ok": bool(text),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Voice transcription failed: {exc}")
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass