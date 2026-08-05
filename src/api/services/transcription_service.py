import os
import json
import traceback
from pathlib import Path
from typing import Optional

import librosa
from dotenv import load_dotenv

# ── Load .env ──────────────────────────────────────────────────
_BASE_DIR = Path(__file__).resolve().parents[3]
load_dotenv(_BASE_DIR / ".env")

DEEPGRAM_API_KEY          = os.getenv("DEEPGRAM_API_KEY", "")
DIARIZATION_THRESHOLD_SEC = 5 * 60   # 5 minutes

print(f"[ASR] Deepgram key found: {'YES' if DEEPGRAM_API_KEY else 'NO'}")

# ── Language maps ──────────────────────────────────────────────
_USER_LANG_LABELS = {
    "fr":  "French",
    "ar":  "Arabic / Tunisian",
    "en":  "English",
    "es":  "Spanish",
    "de":  "German",
    "it":  "Italian",
    "pt":  "Portuguese",
    "nl":  "Dutch",
    "zh":  "Chinese",
    "ja":  "Japanese",
    "ko":  "Korean",
    "ru":  "Russian",
    "tr":  "Turkish",
}

_DEEPGRAM_LANG_MAP = {
    "fr": "fr",
    "ar": "ar",
    "en": "en-US",
    "es": "es",
    "de": "de",
    "it": "it",
    "pt": "pt",
    "nl": "nl",
    "zh": "zh-CN",
    "ja": "ja",
    "ko": "ko",
    "ru": "ru",
    "tr": "tr",
}

# ── Mime map ───────────────────────────────────────────────────
_MIME_MAP = {
    ".wav":  "audio/wav",
    ".mp3":  "audio/mp3",
    ".m4a":  "audio/m4a",
    ".flac": "audio/flac",
    ".ogg":  "audio/ogg",
}


# ══════════════════════════════════════════════════════════════
# DEEPGRAM HELPER — works with any SDK version
# ══════════════════════════════════════════════════════════════
def _call_deepgram(audio_path: str, options: dict) -> dict:
    """
    Call Deepgram REST API directly using httpx.
    SSL verification disabled for Windows corporate environments.
    """
    import httpx

    ext      = Path(audio_path).suffix.lower()
    mimetype = _MIME_MAP.get(ext, "audio/wav")

    with open(audio_path, "rb") as f:
        audio_data = f.read()

    # ✅ Build query string from options
    params = []
    for k, v in options.items():
        params.append(f"{k}={v}")
    query_string = "&".join(params)

    url = f"https://api.deepgram.com/v1/listen?{query_string}"

    print(f"[Deepgram] POST {url[:80]}...")

    # ✅ verify=False fixes SSL issues on Windows / corporate networks
    with httpx.Client(timeout=120.0, verify=False) as client:
        response = client.post(
            url,
            headers={
                "Authorization": f"Token {DEEPGRAM_API_KEY}",
                "Content-Type":  mimetype,
            },
            content=audio_data,
        )
        response.raise_for_status()
        return response.json()


# ══════════════════════════════════════════════════════════════
# STEP 1 — INGESTION
# ══════════════════════════════════════════════════════════════
def ingest_audio(audio_path: str) -> dict:
    """Load and validate audio. Returns duration_sec."""
    print(f"[INGEST] Loading: {audio_path}")
    audio, sr    = librosa.load(audio_path, sr=16000, mono=True)
    duration_sec = round(len(audio) / 16000, 2)
    print(f"[INGEST] Duration: {duration_sec}s | SR: {sr}Hz")
    return {
        "audio_np":     audio,
        "duration_sec": duration_sec,
    }


# ══════════════════════════════════════════════════════════════
# STEP 2 — TRANSCRIPTION
# ══════════════════════════════════════════════════════════════
def transcribe_with_deepgram(audio_path: str, language: Optional[str]) -> dict:
    """Transcribe using Deepgram Nova-2 via direct REST API."""
    print(f"[Deepgram] Transcribing | lang: {language}")

    options = {
        "model":        "nova-2",
        "smart_format": "true",
        "punctuate":    "true",
        "diarize":      "false",
    }
    if language:
        options["language"] = _DEEPGRAM_LANG_MAP.get(language, language)
    else:
        options["detect_language"] = "true"

    data         = _call_deepgram(audio_path, options)
    alternative  = data["results"]["channels"][0]["alternatives"][0]
    text         = alternative.get("transcript", "")
    duration_sec = round(float(data["metadata"].get("duration", 0)), 2)

    detected_lang = (
        data["results"].get("detected_language")
        or language
        or "en"
    )
    lang_label = _USER_LANG_LABELS.get(
        detected_lang,
        detected_lang.title() if detected_lang else "Unknown"
    )

    print(f"[Deepgram] Done! Lang: {lang_label} | Duration: {duration_sec}s | Words: {len(text.split())}")

    return {
        "language":     lang_label,
        "text":         text.strip(),
        "duration_sec": duration_sec,
    }


# ══════════════════════════════════════════════════════════════
# STEP 3a — DIARIZATION via Deepgram (audio > 5 min)
# ══════════════════════════════════════════════════════════════
def diarize_with_deepgram(audio_path: str, language: Optional[str]) -> list:
    """Speaker diarization using Deepgram REST API."""
    print(f"[Deepgram Diarize] Running on: {audio_path}")

    options = {
        "model":        "nova-2",
        "smart_format": "true",
        "punctuate":    "true",
        "diarize":      "true",
    }
    if language:
        options["language"] = _DEEPGRAM_LANG_MAP.get(language, language)
    else:
        options["detect_language"] = "true"

    data  = _call_deepgram(audio_path, options)
    words = data["results"]["channels"][0]["alternatives"][0].get("words", [])

    segments = []
    current  = None

    for w in words:
        speaker = w.get("speaker", 0)
        if current is None or current["speaker_id"] != speaker:
            if current:
                segments.append(current)
            current = {
                "speaker_id": speaker,
                "speaker":    f"Speaker {speaker + 1}",
                "start":      round(float(w.get("start", 0)), 2),
                "end":        round(float(w.get("end",   0)), 2),
                "text":       w.get("word", ""),
            }
        else:
            current["text"] += f" {w.get('word', '')}"
            current["end"]   = round(float(w.get("end", 0)), 2)

    if current:
        segments.append(current)

    for seg in segments:
        seg.pop("speaker_id", None)

    print(f"[Deepgram Diarize] Found {len(segments)} speaker segments")
    return segments


# ══════════════════════════════════════════════════════════════
# STEP 3b — DIARIZATION via Whisper (audio ≤ 5 min)
# ══════════════════════════════════════════════════════════════
_ASR_COMPONENTS = {"processor": None, "model": None, "pipeline": None}

_LOCAL_MODEL = _BASE_DIR / "models" / "whisper-large-v3"
MODEL_ID     = os.getenv(
    "WHISPER_MODEL_ID",
    str(_LOCAL_MODEL) if _LOCAL_MODEL.exists() else "openai/whisper-large-v3",
)

import torch
DEVICE     = "cuda" if torch.cuda.is_available() else "cpu"
TORCH_TYPE = torch.float16 if torch.cuda.is_available() else torch.float32

print(f"[ASR] Whisper device : {DEVICE}")
print(f"[ASR] Whisper model  : {MODEL_ID}")


def _load_whisper():
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

    print("[Whisper] Loading processor...")
    processor = AutoProcessor.from_pretrained(MODEL_ID)

    print("[Whisper] Loading model...")
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        MODEL_ID,
        torch_dtype       = TORCH_TYPE,
        low_cpu_mem_usage = True,
    )
    model.to(DEVICE)

    print("[Whisper] Building pipeline...")
    asr_pipeline = pipeline(
        task              = "automatic-speech-recognition",
        model             = model,
        tokenizer         = processor.tokenizer,
        feature_extractor = processor.feature_extractor,
        torch_dtype       = TORCH_TYPE,
        device            = 0 if DEVICE == "cuda" else -1,
        return_timestamps = True,
    )

    print("[Whisper] Ready!")
    return processor, model, asr_pipeline


def _ensure_whisper_loaded():
    if _ASR_COMPONENTS["pipeline"] is None:
        print("[Whisper] Initializing — may take a few minutes on CPU...")
        try:
            p, m, pipe = _load_whisper()
            _ASR_COMPONENTS["processor"] = p
            _ASR_COMPONENTS["model"]     = m
            _ASR_COMPONENTS["pipeline"]  = pipe
            print("[Whisper] Loaded successfully!")
        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"Whisper failed to load: {e}")


def diarize_with_whisper(audio_path: str, language: Optional[str]) -> list:
    """Timestamp-based segments using local Whisper for audio ≤ 5 minutes."""
    print(f"[Whisper Diarize] Running on: {audio_path}")
    _ensure_whisper_loaded()

    audio, _   = librosa.load(audio_path, sr=16000, mono=True)
    gen_kwargs = {"task": "transcribe", "return_timestamps": True}
    if language:
        gen_kwargs["language"] = language

    result   = _ASR_COMPONENTS["pipeline"](audio, generate_kwargs=gen_kwargs)
    chunks   = result.get("chunks", []) if isinstance(result, dict) else []
    segments = []

    for chunk in chunks:
        ts    = chunk.get("timestamp", (0, 0))
        start = ts[0] if ts[0] is not None else 0
        end   = ts[1] if ts[1] is not None else start + 1
        segments.append({
            "speaker": "Speaker 1",
            "start":   round(float(start), 2),
            "end":     round(float(end),   2),
            "text":    chunk.get("text", "").strip(),
        })

    print(f"[Whisper Diarize] Found {len(segments)} segments")
    return segments


# ══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════
def transcribe_audio_file(audio_path: str, language: Optional[str] = None) -> dict:
    """
    Full pipeline:
    1. Ingest audio
    2. Transcribe with Deepgram Nova-2
    3. Diarize:
       - > 5 min  → Deepgram diarization
       - ≤ 5 min  → Whisper local diarization
    """
    print(f"\n{'='*55}")
    print(f"[PIPELINE] Start | lang: {language}")
    print(f"{'='*55}")

    # ── Step 1: Ingest ────────────────────────────────────────
    ingested     = ingest_audio(audio_path)
    duration_sec = ingested["duration_sec"]

    # ── Step 2: Transcribe ────────────────────────────────────
    if not DEEPGRAM_API_KEY:
        raise RuntimeError("No Deepgram API key found in .env!")

    transcription = transcribe_with_deepgram(audio_path, language)

    # ── Step 3: Diarize ───────────────────────────────────────
    try:
        if duration_sec > DIARIZATION_THRESHOLD_SEC:
            print(f"[PIPELINE] Audio > 5min → Deepgram diarization")
            segments = diarize_with_deepgram(audio_path, language)
        else:
            print(f"[PIPELINE] Audio ≤ 5min → Whisper diarization")
            segments = diarize_with_whisper(audio_path, language)
    except Exception as e:
        print(f"[PIPELINE] Diarization failed: {e} — continuing without segments")
        traceback.print_exc()
        segments = []

    print(f"[PIPELINE] Complete ✅")
    print(f"{'='*55}\n")

    return {
        "language":      transcription["language"],
        "text":          transcription["text"],
        "duration_sec":  duration_sec,
        "segments":      segments,
        "segments_json": json.dumps(segments, ensure_ascii=False),
    }
