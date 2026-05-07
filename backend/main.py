from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

backend_dir = Path(__file__).resolve().parent
workspace_dir = backend_dir.parent

load_dotenv(workspace_dir / ".env")
load_dotenv(backend_dir / ".env", override=True)

from routes.interview import router as interview_router
from routes.resume import router as resume_router
from routes.model_inference import router as model_inference_router
from routes.voice import router as voice_router
from routes.tts import router as tts_router

app = FastAPI(title="AI Interview Lab")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # Allow frontend origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(interview_router, prefix="/api")
app.include_router(resume_router, prefix="/api")
app.include_router(model_inference_router, prefix="/api")
app.include_router(voice_router, prefix="/api")
app.include_router(tts_router, prefix="/api")

@app.get("/")
def root():
    return {"message": "AI Interview Lab Backend Running"}