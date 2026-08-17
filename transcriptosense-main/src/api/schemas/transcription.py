from pydantic import BaseModel
from typing import Optional


class TranscriptionResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    id:              Optional[int]   = None
    filename:        str
    language:        str
    transcription:   str
    original_text:   Optional[str]   = None
    diarized_text:   Optional[str]   = None
    plain_text:      Optional[str]   = None
    model_used:      Optional[str]   = "whisper-small"
    file_size:       Optional[str]   = None
    duration_sec:    Optional[float] = 0.0
    speakers_count:  Optional[int]   = None
    has_diarization: Optional[bool]  = False
    created_at:      Optional[str]   = None
