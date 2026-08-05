from pydantic import BaseModel
from typing import Optional


class TranscriptionResponse(BaseModel):
    id:              Optional[int]   = None
    filename:        str
    language:        str
    transcription:   str
    cleaned_text:    Optional[str]   = None
    translated_text: Optional[str]   = None
    summary:         Optional[str]   = None
    segments:        Optional[str]   = None
    model_used:      Optional[str]   = "deepgram-nova-2"
    file_size:       Optional[str]   = None
    duration_sec:    Optional[float] = 0.0
    created_at:      Optional[str]   = None
