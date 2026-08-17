import json
import os
from pathlib import Path
from typing import List, Dict, Any

def _fallback_from_vad(vad_json_path: str) -> Dict[str, Any]:
    # Read VAD JSON created by preprocess and turn segments into single-speaker diarization
    if not Path(vad_json_path).exists():
        return {"has_diarization": False, "speakers": None}
    doc = json.loads(Path(vad_json_path).read_text(encoding="utf-8"))
    segments = doc.get("speech_segments", [])
    speakers = []
    for i, s in enumerate(segments):
        speakers.append({
            "speaker": 0,
            "start": s.get("start", 0.0),
            "end": s.get("end", 0.0),
            "text": None,
        })
    return {"has_diarization": False, "speakers": speakers}


def diarize_audio(audio_path: str, vad_json_path: str = None) -> Dict[str, Any]:
    """Try to run speaker diarization using `pyannote.audio` when available.

    If `pyannote` is not installed or fails, fall back to VAD segments as single-speaker ranges.
    Returns a dict with keys: `has_diarization` (bool) and `speakers` (list of speaker dicts).
    """
    # Try pyannote first
    try:
        from pyannote.audio import Pipeline
    except Exception:
        # No pyannote available — fallback
        return _fallback_from_vad(vad_json_path or "")

    try:
        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization")
        diarization = pipeline(audio_path)

        speakers = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            speakers.append({
                "speaker": speaker,
                "start": float(turn.start),
                "end": float(turn.end),
                "text": None,
            })

        return {"has_diarization": True, "speakers": speakers}
    except Exception:
        # On any failure, fallback to VAD-derived segments
        return _fallback_from_vad(vad_json_path or "")
