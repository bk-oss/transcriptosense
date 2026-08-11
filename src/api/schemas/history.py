from pydantic import BaseModel
from typing import Optional, List


class TranscriptionRecord(BaseModel):
    model_config = {"protected_namespaces": ()}

    id:              int
    filename:        str
    language:        Optional[str]   = None
    transcription:   Optional[str]   = None
    model_used:      Optional[str]   = None
    file_size:       Optional[str]   = None
    duration_sec:    Optional[float] = 0.0
    speakers_count:  Optional[int]   = 0
    has_diarization: Optional[bool]  = False
    created_at:      Optional[str]   = None


class HistoryResponse(BaseModel):
    total:   int
    records: List[TranscriptionRecord]


class DeleteResponse(BaseModel):
    success: bool
    message: str
