from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from src.api.schemas.history import HistoryResponse, TranscriptionRecord, DeleteResponse
from src.api.services.database import (
    get_all_transcriptions,
    get_transcription_by_id,
    delete_transcription,
    clear_all_transcriptions,
    search_transcriptions,
)

router = APIRouter(tags=["History"])


@router.get("/history", response_model=HistoryResponse)
def get_history():
    records = get_all_transcriptions()
    return HistoryResponse(
        total=len(records),
        records=[TranscriptionRecord(**r) for r in records],
    )


@router.get("/history/search", response_model=HistoryResponse)
def search_history(q: str):
    if not q or len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters.")
    records = search_transcriptions(q.strip())
    return HistoryResponse(
        total=len(records),
        records=[TranscriptionRecord(**r) for r in records],
    )


@router.get("/history/{transcription_id}/download")
def download_transcription(transcription_id: int):
    record = get_transcription_by_id(transcription_id)
    if not record:
        raise HTTPException(status_code=404, detail="Transcription not found.")

    dur = record.get("duration_sec") or 0
    m, s = divmod(int(dur), 60)
    dur_str = f"{m}m {s:02d}s" if m else f"{s}s"

    content = (
        f"TRANSCRIPTOSENSE — Transcription Report\n"
        f"{'=' * 44}\n"
        f"ID          : {record['id']}\n"
        f"Filename    : {record['filename']}\n"
        f"Language    : {record['language']}\n"
        f"Model       : {record['model_used']}\n"
        f"File Size   : {record['file_size']}\n"
        f"Duration    : {dur_str}\n"
        f"Created At  : {record['created_at']}\n"
        f"{'=' * 44}\n\n"
        f"{record['transcription']}\n"
    )

    filename = f"transcription_{record['id']}_{record['filename']}.txt"
    return PlainTextResponse(
        content=content,
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


@router.get("/history/{transcription_id}", response_model=TranscriptionRecord)
def get_one(transcription_id: int):
    record = get_transcription_by_id(transcription_id)
    if not record:
        raise HTTPException(status_code=404, detail="Transcription not found.")
    return TranscriptionRecord(**record)


@router.delete("/history", response_model=DeleteResponse)
def clear_all():
    count = clear_all_transcriptions()
    return DeleteResponse(success=True, message=f"Cleared {count} transcription(s).")


@router.delete("/history/{transcription_id}", response_model=DeleteResponse)
def delete_one(transcription_id: int):
    success = delete_transcription(transcription_id)
    if not success:
        raise HTTPException(status_code=404, detail="Transcription not found.")
    return DeleteResponse(
        success=True,
        message=f"Transcription {transcription_id} deleted successfully.",
    )
