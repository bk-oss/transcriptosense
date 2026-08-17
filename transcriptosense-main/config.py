"""
TranscriptoSense — Central Configuration
All paths, model names, and hyperparameters live here.
Import this in any module: from config import CFG

Importing this module automatically:
  - loads .env (HuggingFace token, etc.)
  - configures ffmpeg (no PATH edit needed)
  - sets up logging
"""

import os
import sys
from pathlib import Path

# ─────────────────────────────────────────────
# Load .env
# ─────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed yet — fine during early setup

HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


# ─────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).parent

DATA_RAW        = BASE_DIR / "data" / "raw"
DATA_PROCESSED  = BASE_DIR / "data" / "processed"
DATA_ANNOTATIONS= BASE_DIR / "data" / "annotations"

MODELS_DIR      = BASE_DIR / "models"

OUT_TRANSCRIPTS = BASE_DIR / "outputs" / "transcripts"
OUT_SUMMARIES   = BASE_DIR / "outputs" / "summaries"
OUT_EXPORTS     = BASE_DIR / "outputs" / "exports"

LOGS_DIR        = BASE_DIR / "logs"

# Create all directories if they don't exist
for _dir in [DATA_RAW, DATA_PROCESSED, DATA_ANNOTATIONS, MODELS_DIR,
             OUT_TRANSCRIPTS, OUT_SUMMARIES, OUT_EXPORTS, LOGS_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────
# Logging — centralized, used by every module
# Usage in any file: from config import get_logger
#                     log = get_logger(__name__)
# ─────────────────────────────────────────────
def get_logger(name: str = "transcriptosense"):
    """Returns a loguru-based logger writing to console + a rotating file."""
    try:
        from loguru import logger
        # Avoid adding duplicate sinks if get_logger() is called many times
        if not getattr(get_logger, "_configured", False):
            logger.remove()  # remove default handler
            logger.add(sys.stderr, level=LOG_LEVEL,
                       format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>")
            logger.add(LOGS_DIR / "transcriptosense_{time:YYYY-MM-DD}.log",
                       level="DEBUG", rotation="10 MB", retention="14 days",
                       encoding="utf-8")
            get_logger._configured = True
        return logger.bind(module=name)
    except ImportError:
        # Fallback to stdlib logging if loguru isn't installed yet
        import logging
        logging.basicConfig(level=LOG_LEVEL)
        return logging.getLogger(name)


log = get_logger("config")


# ─────────────────────────────────────────────
# FFmpeg — set direct path since PATH cannot be edited on this machine
# (no admin rights available). Update this path if ffmpeg moves.
# Auto-configured on import — no need to call this manually.
# ─────────────────────────────────────────────
FFMPEG_DIR = Path(
    os.getenv("FFMPEG_DIR") or
    r"C:\Users\mbaklouti1\Downloads\ffmpeg-8.1.2-essentials_build"
    r"\ffmpeg-8.1.2-essentials_build\bin"
)
FFMPEG_EXE = FFMPEG_DIR / "ffmpeg.exe"
FFPROBE_EXE = FFMPEG_DIR / "ffprobe.exe"

def configure_ffmpeg():
    """Point pydub (and anything else that needs it) directly at ffmpeg.exe,
    bypassing PATH entirely. Called automatically on import."""
    if not FFMPEG_EXE.exists():
        log.warning(f"ffmpeg.exe not found at {FFMPEG_EXE} — "
                    f"set FFMPEG_DIR in .env or update config.py")
        return False
    os.environ["PATH"] += os.pathsep + str(FFMPEG_DIR)  # session-only, safe
    try:
        from pydub import AudioSegment
        AudioSegment.converter = str(FFMPEG_EXE)
        AudioSegment.ffprobe = str(FFPROBE_EXE)
    except ImportError:
        pass  # pydub not installed yet — fine during early setup
    return True

_ffmpeg_ok = configure_ffmpeg()


# ─────────────────────────────────────────────
# Audio Preprocessing
# ─────────────────────────────────────────────
AUDIO = {
    "sample_rate": 16000,       # Whisper expects 16kHz
    "channels": 1,              # Mono
    "chunk_duration_sec": 30,   # Process audio in 30s chunks
    "vad_aggressiveness": 2,    # webrtcvad: 0 (least) to 3 (most aggressive)
    "supported_formats": [".wav", ".mp3", ".m4a", ".ogg", ".flac", ".mp4"],
}


# ─────────────────────────────────────────────
# ASR (Speech-to-Text)
# ─────────────────────────────────────────────
ASR = {
    # Model size tradeoff:
    #   tiny / base  → fast, lower accuracy  (good for CPU testing)
    #   small        → balanced              (recommended for CPU)
    #   medium       → better, needs GPU
    #   large-v3     → best, needs GPU       (use in Colab)
    "model_size": "small",          # Change to "large-v3" in Colab
    "device": "cpu",                # "cuda" in Colab
    "compute_type": "int8",         # "float16" on GPU, "int8" on CPU
    "language": None,               # None = auto-detect per segment
    "task": "transcribe",           # "transcribe" or "translate"
    "beam_size": 5,
    "word_timestamps": True,        # Required for clickable timestamp links
    "condition_on_previous_text": True,
    "initial_prompt": (             # Hints the model toward FR/AR/Darija
        "Transcription d'une réunion en français, arabe et darija marocain. "
        "Les locuteurs peuvent alterner entre les langues."
    ),
}


# ─────────────────────────────────────────────
# Diarization (Silver tier)
# ─────────────────────────────────────────────
DIARIZATION = {
    # pyannote/speaker-diarization-3.1 requires HuggingFace token
    # Set your token in .env: HUGGINGFACE_TOKEN=hf_xxx
    "model": "pyannote/speaker-diarization-3.1",
    "min_speakers": 1,
    "max_speakers": 10,
    "min_duration_on": 0.5,    # seconds — ignore very short segments
    "min_duration_off": 0.3,   # seconds — merge very short silences
}


# ─────────────────────────────────────────────
# NLP / Semantic layers (Silver tier)
# ─────────────────────────────────────────────
NLP = {
    # NER — multilingual model that handles FR/AR
    "ner_model": "Davlan/bert-base-multilingual-cased-ner-hrl",

    # Embeddings for topic clustering / keyword extraction
    "embedding_model": "intfloat/multilingual-e5-base",

    # Summarization
    "summarization_model": "csebuetnlp/mT5_multilingual_XLSum",

    # Keyword extraction method: "keybert" or "tfidf"
    "keyword_method": "tfidf",      # Start with tfidf (no GPU needed)
    "top_k_keywords": 10,

    # Sentiment
    "sentiment_model": "cardiffnlp/twitter-xlm-roberta-base-sentiment",

    # Action item / decision detection (Bronze: rule-based, Silver: model)
    "action_item_method": "rules",  # "rules" or "classifier"
}


# ─────────────────────────────────────────────
# Languages & Code-Switching
# ─────────────────────────────────────────────
LANGUAGES = {
    "supported": ["fr", "ar", "darija"],
    "whisper_codes": {
        "fr": "fr",
        "ar": "ar",
        "darija": "ar",     # Whisper has no Darija code; use AR as closest
    },
    # Darija-specific: common romanized tokens to flag for normalization
    "darija_markers": ["walakin", "bzzaf", "mzyan", "zwina", "kifash", "hta"],
}


# ─────────────────────────────────────────────
# Bronze-tier rule patterns
# Patterns for detecting decisions and action items in transcript text
# ─────────────────────────────────────────────
RULES = {
    "decision_patterns_fr": [
        r"\bon a décidé\b", r"\bil est décidé\b", r"\bnous allons\b",
        r"\bla décision est\b", r"\bconclusion\b", r"\bfinalement\b",
        r"\baccord sur\b", r"\bvalidé\b",
    ],
    "decision_patterns_ar": [
        r"\bتم الاتفاق\b", r"\bقررنا\b", r"\bتقرر\b", r"\bالقرار\b",
    ],
    "action_patterns_fr": [
        r"\btu dois\b", r"\bvous devez\b", r"\bil faut\b", r"\bà faire\b",
        r"\baction\b", r"\btâche\b", r"\bresponsable\b", r"\bdelai\b",
        r"\bprendre en charge\b", r"\bje vais\b", r"\bon va\b",
    ],
    "action_patterns_ar": [
        r"\bيجب\b", r"\bلازم\b", r"\bمهمة\b", r"\bسنقوم\b",
    ],
    # Darija (romanized approximations)
    "action_patterns_darija": [
        r"\bkhassna\b", r"\bdir\b", r"\bndir\b", r"\bghadi ndiru\b",
    ],
}


# ─────────────────────────────────────────────
# Output / Export
# ─────────────────────────────────────────────
EXPORT = {
    "formats": ["json", "docx", "pdf"],
    "include_timestamps": True,
    "include_speaker_labels": True,
    "minutes_template": "formal",       # "formal" or "brief"
    "csv_tasks": True,                  # Export action items as CSV
    "ics_tasks": False,                 # Export as calendar (.ics) — Silver tier
}


# ─────────────────────────────────────────────
# API (FastAPI)
# ─────────────────────────────────────────────
API = {
    "host": "0.0.0.0",
    "port": 8000,
    "max_upload_mb": 200,
    "allowed_extensions": AUDIO["supported_formats"],
}


# ─────────────────────────────────────────────
# Evaluation
# ─────────────────────────────────────────────
EVAL = {
    "wer_threshold_acceptable": 0.25,   # 25% WER = acceptable for noisy audio
    "der_threshold_acceptable": 0.20,   # 20% DER = acceptable
    "rouge_l_min": 0.30,                # Minimum ROUGE-L for summaries
}


# ─────────────────────────────────────────────
# Convenience object — import as: from config import CFG
# ─────────────────────────────────────────────
class CFG:
    BASE_DIR       = BASE_DIR
    DATA_RAW       = DATA_RAW
    DATA_PROCESSED = DATA_PROCESSED
    DATA_ANNOTATIONS = DATA_ANNOTATIONS
    MODELS_DIR     = MODELS_DIR
    OUT_TRANSCRIPTS = OUT_TRANSCRIPTS
    OUT_SUMMARIES  = OUT_SUMMARIES
    OUT_EXPORTS    = OUT_EXPORTS
    LOGS_DIR       = LOGS_DIR

    audio       = AUDIO
    asr         = ASR
    diarization = DIARIZATION
    nlp         = NLP
    languages   = LANGUAGES
    rules       = RULES
    export      = EXPORT
    api         = API
    eval        = EVAL
    paths = {
        "base":         BASE_DIR,
        "raw":          DATA_RAW,
        "processed":    DATA_PROCESSED,
        "annotations":  DATA_ANNOTATIONS,
        "models":       MODELS_DIR,
        "transcripts":  OUT_TRANSCRIPTS,
        "summaries":    OUT_SUMMARIES,
        "exports":      OUT_EXPORTS,
    }


if __name__ == "__main__":
    print("TranscriptoSense Config loaded successfully.")
    print(f"  Base dir     : {BASE_DIR}")
    print(f"  ASR model    : {ASR['model_size']} ({ASR['device']})")
    print(f"  Languages    : {LANGUAGES['supported']}")
    print(f"  ffmpeg found : {_ffmpeg_ok} ({FFMPEG_EXE})")
    print(f"  HF token set : {bool(HUGGINGFACE_TOKEN)}")
    print(f"  Logs dir     : {LOGS_DIR}")

