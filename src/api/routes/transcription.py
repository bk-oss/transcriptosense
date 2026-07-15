import os
from uuid import uuid4
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from src.api.schemas.transcription import TranscriptionResponse
from src.api.services.transcription_service import transcribe_audio_file
from src.api.services.database import save_transcription

router = APIRouter(tags=["Transcription"])

# ── Portable upload directory ─────────────────────────────────────────────────
# routes/ → api/ → src/ → project root
_BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
UPLOAD_DIR = str(_BASE_DIR / "data" / "interim")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),   # "fr" | "ar" | "" → auto-detect
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    allowed_extensions = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}
    _, ext = os.path.splitext(file.filename.lower())

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {ext}. Supported: WAV, MP3, M4A, FLAC, OGG"
        )

    temp_filename = f"{uuid4()}{ext}"
    temp_path = os.path.join(UPLOAD_DIR, temp_filename)

    try:
        content = await file.read()
        file_size_str = _format_bytes(len(content))

        with open(temp_path, "wb") as buffer:
            buffer.write(content)

        lang_hint = language.strip() if language and language.strip() else None
        result = transcribe_audio_file(temp_path, language=lang_hint)

        record_id = save_transcription(
            filename=file.filename,
            language=result.get("language", "unknown"),
            transcription=result.get("text", ""),
            file_size=file_size_str,
            duration_sec=result.get("duration_sec", 0.0),
        )

        return TranscriptionResponse(
            id=record_id,
            filename=file.filename,
            language=result.get("language", "unknown"),
            transcription=result.get("text", ""),
            model_used="whisper-large-v3",
            file_size=file_size_str,
            duration_sec=result.get("duration_sec", 0.0),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def _format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 ** 2):.1f} MB"
