import os
import shutil
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from src.api.schemas.transcription import TranscriptionResponse
from src.api.services.transcription_service import transcribe_audio_file
from src.api.services.database import save_transcription

router = APIRouter(tags=["Transcription"])

UPLOAD_DIR = r"C:\Users\mbaklouti1\Desktop\transcriptosense\data\interim"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    allowed_extensions = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}
    _, ext = os.path.splitext(file.filename.lower())

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {ext}"
        )

    temp_filename = f"{uuid4()}{ext}"
    temp_path = os.path.join(UPLOAD_DIR, temp_filename)

    try:
        content = await file.read()
        file_size_str = format_bytes(len(content))

        with open(temp_path, "wb") as buffer:
            buffer.write(content)

        result = transcribe_audio_file(temp_path)

        record_id = save_transcription(
            filename=file.filename,
            language=result.get("language", "unknown"),
            transcription=result.get("text", ""),
            file_size=file_size_str
        )

        return TranscriptionResponse(
            id=record_id,
            filename=file.filename,
            language=result.get("language", "unknown"),
            transcription=result.get("text", ""),
            model_used="whisper-large-v3",
            file_size=file_size_str
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 ** 2):.1f} MB"
