import os
import json
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

        # Extract speakers count from diarization data
        speakers_count = 0
        if result.get("speakers"):
            try:
                speakers_data = json.loads(result["speakers"]) if isinstance(result["speakers"], str) else result["speakers"]
                speakers_count = len(set(s.get("speaker") for s in speakers_data))
            except Exception:
                speakers_count = 0

        model_used = result.get("model_used", "whisper-small")
        has_diarization = result.get("has_diarization", False)

        record_id = save_transcription(
            filename=file.filename,
            language=result.get("language", "unknown"),
            transcription=result.get("text", ""),
            model_used=model_used,
            file_size=file_size_str,
            duration_sec=result.get("duration_sec", 0.0),
            speakers_count=speakers_count,
            has_diarization=has_diarization,
        )

        return TranscriptionResponse(
            id=record_id,
            filename=file.filename,
            language=result.get("language", "unknown"),
            transcription=result.get("text", ""),
            model_used=model_used,
            file_size=file_size_str,
            duration_sec=result.get("duration_sec", 0.0),
            speakers_count=speakers_count if speakers_count > 0 else None,
            has_diarization=has_diarization,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {str(e)}"
        )

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
