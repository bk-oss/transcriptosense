from pydantic import BaseModel
from typing import Optional, List


class TranscriptionRecord(BaseModel):
    id: int
    filename: str
    language: Optional[str] = None
    transcription: Optional[str] = None
    model_used: Optional[str] = None
    file_size: Optional[str] = None
    created_at: Optional[str] = None


class HistoryResponse(BaseModel):
    total: int
    records: List[TranscriptionRecord]


class DeleteResponse(BaseModel):
    success: bool
    message: str
