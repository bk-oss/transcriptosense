from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from src.api.services.database import (
    get_all_transcriptions,
    get_transcription_by_id,
    delete_transcription,
    clear_all_transcriptions,
    search_transcriptions,
)
from src.api.schemas.history import HistoryResponse, TranscriptionRecord, DeleteResponse

router = APIRouter(tags=["History"])


@router.get("/history", response_model=HistoryResponse)
def get_history(
    search: Optional[str] = Query(None, description="Search in transcription text or filename"),
):
    """Get all transcriptions, optionally filtered by search query."""
    if search and search.strip():
        records = search_transcriptions(search.strip())
    else:
        records = get_all_transcriptions()

    return HistoryResponse(
        total   = len(records),
        records = [TranscriptionRecord(**r) for r in records],
    )


@router.get("/history/{transcription_id}", response_model=TranscriptionRecord)
def get_single(transcription_id: int):
    """Get a single transcription by ID."""
    record = get_transcription_by_id(transcription_id)
    if not record:
        raise HTTPException(status_code=404, detail="Transcription not found.")
    return TranscriptionRecord(**record)


@router.delete("/history/{transcription_id}", response_model=DeleteResponse)
def delete_single(transcription_id: int):
    """Delete a single transcription by ID."""
    success = delete_transcription(transcription_id)
    if not success:
        raise HTTPException(status_code=404, detail="Transcription not found.")
    return DeleteResponse(
        success = True,
        message = f"Transcription {transcription_id} deleted successfully.",
    )


@router.delete("/history", response_model=DeleteResponse)
def delete_all():
    """Delete all transcriptions."""
    count = clear_all_transcriptions()
    return DeleteResponse(
        success = True,
        message = f"{count} transcription(s) deleted successfully.",
    )
