from pydantic import BaseModel
from typing import Optional


class TranscriptionResponse(BaseModel):
    id:            Optional[int]   = None
    filename:      str
    language:      str
    transcription: str
    model_used:    Optional[str]   = "whisper-large-v3"
    file_size:     Optional[str]   = None
    duration_sec:  Optional[float] = 0.0
    created_at:    Optional[str]   = None
