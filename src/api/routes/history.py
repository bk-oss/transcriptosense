from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from src.api.services import database
from src.api.schemas.history import HistoryResponse, TranscriptionRecord, DeleteResponse

router = APIRouter(tags=["History"])


@router.get("/history", response_model=HistoryResponse)
def get_history(
    search: Optional[str] = Query(None, description="Search in transcription text or filename"),
):
    """Get all transcriptions, optionally filtered by search query."""
    if search and search.strip():
        records = database.search_transcriptions(search.strip())
    else:
        records = database.get_all_transcriptions()

    return HistoryResponse(
        total   = len(records),
        records = [TranscriptionRecord(**r) for r in records],
    )


@router.get("/history/search", response_model=HistoryResponse)
def search_history(
    q: str = Query(..., description="Search query text"),
):
    """Search transcriptions by query string."""
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters.")

    records = database.search_transcriptions(query)
    return HistoryResponse(
        total   = len(records),
        records = [TranscriptionRecord(**r) for r in records],
    )


@router.get("/history/{transcription_id}", response_model=TranscriptionRecord)
def get_single(transcription_id: int):
    """Get a single transcription by ID."""
    record = database.get_transcription_by_id(transcription_id)
    if not record:
        raise HTTPException(status_code=404, detail="Transcription not found.")
    return TranscriptionRecord(**record)


@router.delete("/history/{transcription_id}", response_model=DeleteResponse)
def delete_single(transcription_id: int):
    """Delete a single transcription by ID."""
    success = database.delete_transcription(transcription_id)
    if not success:
        raise HTTPException(status_code=404, detail="Transcription not found.")
    return DeleteResponse(
        success = True,
        message = f"Transcription {transcription_id} deleted successfully.",
    )


@router.delete("/history", response_model=DeleteResponse)
def delete_all():
    """Delete all transcriptions."""
    count = database.clear_all_transcriptions()
    return DeleteResponse(
        success = True,
        message = f"{count} transcription(s) deleted successfully.",
    )
