import os
import json
import traceback
from uuid import uuid4
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from src.api.schemas.transcription import TranscriptionResponse
from src.api.services.database import save_transcription, get_transcription_by_id
from src.api.services.transcription_service import transcribe_audio_file

router = APIRouter(tags=["Transcription"])

_BASE_DIR  = Path(__file__).resolve().parents[3]
UPLOAD_DIR = str(_BASE_DIR / "data" / "interim")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(
    file:         UploadFile    = File(...),
    language:     Optional[str] = Form(None),
    clean:        bool          = Form(True),
    translate_to: Optional[str] = Form(None),
    summarize:    bool          = Form(False),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    allowed_extensions = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}
    _, ext = os.path.splitext(file.filename.lower())

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {ext}. Supported: WAV, MP3, M4A, FLAC, OGG"
        )

    temp_filename = f"{uuid4()}{ext}"
    temp_path     = os.path.join(UPLOAD_DIR, temp_filename)

    try:
        content       = await file.read()
        file_size_str = _format_bytes(len(content))

        with open(temp_path, "wb") as buffer:
            buffer.write(content)

        lang_hint = language.strip() if language and language.strip() else None

        # ── Step 1+2+3: Ingest + Transcribe + Diarize ─────────
        print(f"[ROUTE] Starting pipeline for: {file.filename}")
        result = await run_in_threadpool(
            transcribe_audio_file, temp_path, lang_hint
        )

        if not result or not isinstance(result, dict):
            raise HTTPException(status_code=500, detail="Transcription failed.")

        # ── Step 4: NLP (optional — only if Ollama available) ──
        cleaned_text    = None
        translated_text = None
        summary_text    = None

        if clean or translate_to or summarize:
            try:
                import httpx as _httpx
                # ✅ Quick check if Ollama is running
                async with _httpx.AsyncClient(timeout=2.0, verify=False) as client:
                    r = await client.get("http://localhost:11434/api/tags")
                    r.raise_for_status()

                from src.api.routes.ollama import _ask_ollama, MODEL_NAME
                raw_text = result.get("text", "")

                if clean:
                    prompt = f"""Clean this transcription — remove fillers, fix grammar, keep original language.
Return ONLY the cleaned text.

Text:
{raw_text}"""
                    cleaned_text = await run_in_threadpool(_ask_ollama, prompt)
                    print(f"[NLP] Cleaned ✅")

                if translate_to:
                    source = cleaned_text or raw_text
                    prompt = f"""Translate to {translate_to}. Return ONLY the translation.

Text:
{source}"""
                    translated_text = await run_in_threadpool(_ask_ollama, prompt)
                    print(f"[NLP] Translated to {translate_to} ✅")

                if summarize:
                    source = cleaned_text or raw_text
                    prompt = f"""Summarize in 3-5 sentences. Return ONLY the summary.

Text:
{source}"""
                    summary_text = await run_in_threadpool(_ask_ollama, prompt)
                    print(f"[NLP] Summarized ✅")

            except Exception as e:
                print(f"[NLP] Skipped — Ollama not available: {e}")

        # ── Step 5: Save to DB ────────────────────────────────
        record_id = save_transcription(
            filename        = file.filename,
            language        = result.get("language", "unknown"),
            transcription   = result.get("text", ""),
            file_size       = file_size_str,
            duration_sec    = result.get("duration_sec", 0.0),
            cleaned_text    = cleaned_text,
            translated_text = translated_text,
            summary         = summary_text,
            segments        = result.get("segments_json"),
            model_used      = "deepgram-nova-2",
        )

        saved_record = get_transcription_by_id(record_id)
        if not saved_record:
            raise HTTPException(status_code=500, detail="Failed to save record.")

        # ── Step 6: Generate PDF ──────────────────────────────
        try:
            from src.api.services.pdf_service import generate_pdf
            segments = result.get("segments", [])
            await run_in_threadpool(
                generate_pdf,
                saved_record,
                segments,
                cleaned_text,
                translated_text,
                summary_text,
            )
            print(f"[PDF] Generated for id={record_id} ✅")
        except Exception as e:
            print(f"[PDF] Generation failed (non-blocking): {e}")
            traceback.print_exc()

        return TranscriptionResponse(**saved_record)

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.get("/transcribe/{transcription_id}/pdf")
async def download_pdf(transcription_id: int):
    """Download the PDF report for a transcription."""
    record = get_transcription_by_id(transcription_id)
    if not record:
        raise HTTPException(status_code=404, detail="Transcription not found.")

    pdf_path = (
        _BASE_DIR / "data" / "reports" /
        f"report_{record['id']}_{record['filename']}.pdf"
    )

    if not pdf_path.exists():
        raise HTTPException(
            status_code=404,
            detail="PDF not yet generated for this transcription."
        )

    return FileResponse(
        path       = str(pdf_path),
        media_type = "application/pdf",
        filename   = f"transcription_{transcription_id}.pdf",
    )


def _format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 ** 2):.1f} MB"
