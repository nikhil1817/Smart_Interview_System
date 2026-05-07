from fastapi import APIRouter, UploadFile, File, HTTPException
from services.resume_parser import ResumeParser

router = APIRouter()
parser = ResumeParser()

@router.post("/parse-resume")
async def parse_resume(file: UploadFile = File(...)):
    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    data = parser.parse_upload(content, file.filename or "")

    return {
        "message": "Resume processed",
        "data": data
    }