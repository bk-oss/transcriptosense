"""
TranscriptoSense — Transcription Service

Smart routing:
  - Audio > 5 minutes  → Deepgram Nova-3 (cloud, with diarization)
  - Audio ≤ 5 minutes  → Whisper small (local CPU)
  - Fallback: if Deepgram fails → Whisper
"""

import os
import json
from pathlib import Path

# ── Thresholds ────────────────────────────────────────────────────────────────
DURATION_THRESHOLD_SEC = 5 * 60  # 5 minutes

# ── Deepgram setup ────────────────────────────────────────────────────────────
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
_deepgram_client = None

def _get_deepgram_client():
    """Lazy-init Deepgram client."""
    global _deepgram_client
    if _deepgram_client is None and DEEPGRAM_API_KEY:
        from deepgram import DeepgramClient
        _deepgram_client = DeepgramClient(DEEPGRAM_API_KEY)
        print("[ASR] Deepgram client initialized.")
    return _deepgram_client


# ── Whisper setup (lazy load) ─────────────────────────────────────────────────
_whisper_pipeline = None
_whisper_processor = None
_whisper_model = None

def _get_whisper_pipeline():
    """Lazy-load Whisper model only when needed."""
    import torch
    import librosa
    global _whisper_pipeline, _whisper_processor, _whisper_model
    if _whisper_pipeline is not None:
        return _whisper_pipeline, _whisper_processor, _whisper_model

    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

    _BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
    _LOCAL_MODEL = _BASE_DIR / "models" / "whisper-small"
    MODEL_ID = os.getenv(
        "WHISPER_MODEL_ID",
        str(_LOCAL_MODEL) if _LOCAL_MODEL.exists() else "openai/whisper-small"
    )

    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    TORCH_TYPE = torch.float16 if torch.cuda.is_available() else torch.float32

    print(f"[ASR] Loading Whisper: {MODEL_ID} on {DEVICE}")

    _whisper_processor = AutoProcessor.from_pretrained(MODEL_ID)
    _whisper_model = AutoModelForSpeechSeq2Seq.from_pretrained(
        MODEL_ID,
        torch_dtype=TORCH_TYPE,
        low_cpu_mem_usage=True,
        use_safetensors=True,
    )
    _whisper_model.to(DEVICE)

    _whisper_pipeline = pipeline(
        task="automatic-speech-recognition",
        model=_whisper_model,
        tokenizer=_whisper_processor.tokenizer,
        feature_extractor=_whisper_processor.feature_extractor,
        torch_dtype=TORCH_TYPE,
        device=DEVICE,
    )

    print("[ASR] Whisper pipeline ready.")
    return _whisper_pipeline, _whisper_processor, _whisper_model


# ── Language maps ─────────────────────────────────────────────────────────────
_LANG_TOKEN_MAP = {
    "<|fr|>": "French", "<|ar|>": "Arabic", "<|en|>": "English",
    "<|es|>": "Spanish", "<|de|>": "German", "<|it|>": "Italian",
    "<|pt|>": "Portuguese", "<|nl|>": "Dutch", "<|zh|>": "Chinese",
    "<|ja|>": "Japanese", "<|ko|>": "Korean", "<|ru|>": "Russian",
    "<|tr|>": "Turkish",
}

_USER_LANG_LABELS = {
    "fr": "French",
    "ar": "Arabic / Tunisian",
    "en": "English",
}


# ── Deepgram transcription ────────────────────────────────────────────────────
def _transcribe_deepgram(audio_path: str, language: str = None) -> dict:
    """Transcribe using Deepgram Nova-3 with diarization."""
    from deepgram import PrerecordedOptions, FileSource

    client = _get_deepgram_client()
    if not client:
        raise RuntimeError("Deepgram API key not configured")

    with open(audio_path, "rb") as f:
        buffer_data = f.read()

    payload = {"buffer": buffer_data}

    options_dict = {
        "model": "nova-3",
        "smart_format": True,
        "diarize": True,
        "utterances": True,
        "paragraphs": True,
    }

    if language and language.strip():
        options_dict["language"] = language
    else:
        options_dict["detect_language"] = True

    options = PrerecordedOptions(**options_dict)

    print(f"[ASR] Deepgram: sending {audio_path}")
    response = client.listen.rest.v("1").transcribe_file(payload, options)

    # Extract transcript
    channel = response.results.channels[0]
    alt = channel.alternatives[0]
    full_text = alt.transcript or ""

    # Extract detected language
    detected_lang = "Unknown"
    if hasattr(channel, 'detected_language') and channel.detected_language:
        detected_lang = channel.detected_language
    elif hasattr(response, 'metadata') and hasattr(response.metadata, 'language'):
        detected_lang = response.metadata.language or "Unknown"

    # Map language codes to labels
    lang_labels = {
        "fr": "French", "ar": "Arabic", "en": "English",
        "es": "Spanish", "de": "German", "it": "Italian",
        "pt": "Portuguese", "nl": "Dutch", "zh": "Chinese",
        "ja": "Japanese", "ko": "Korean", "ru": "Russian",
        "tr": "Turkish",
    }
    if language:
        lang_label = _USER_LANG_LABELS.get(language, language.title())
    else:
        lang_label = lang_labels.get(detected_lang, detected_lang.title() if isinstance(detected_lang, str) else "Unknown")

    # Build diarized transcript from utterances
    speakers_data = []
    diarized_text = full_text  # fallback

    if hasattr(response.results, 'utterances') and response.results.utterances:
        lines = []
        for utt in response.results.utterances:
            speaker_id = utt.speaker
            start_time = utt.start
            end_time = utt.end
            text = utt.transcript
            lines.append(f"Speaker {speaker_id}: {text}")
            speakers_data.append({
                "speaker": speaker_id,
                "start": start_time,
                "end": end_time,
                "text": text,
            })
        diarized_text = "\n".join(lines)

    duration = response.metadata.duration if hasattr(response.metadata, 'duration') else 0

    return {
        "language": lang_label,
        "text": diarized_text.strip(),
        "plain_text": full_text.strip(),
        "duration_sec": round(duration, 2),
        "model_used": "deepgram-nova-3",
        "speakers": json.dumps(speakers_data) if speakers_data else None,
        "has_diarization": bool(speakers_data),
    }


# ── Whisper transcription ─────────────────────────────────────────────────────
def _transcribe_whisper(audio_path: str, language: str = None) -> dict:
    """Transcribe using local Whisper model."""
    import torch
    import librosa
    asr_pipe, processor, model = _get_whisper_pipeline()

    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    TORCH_TYPE = torch.float16 if torch.cuda.is_available() else torch.float32

    audio, _ = librosa.load(audio_path, sr=16000, mono=True)
    duration_sec = round(len(audio) / 16000, 2)

    gen_kwargs = {"task": "transcribe"}

    if language:
        gen_kwargs["language"] = language
        lang_label = _USER_LANG_LABELS.get(language, language.title())
    else:
        # Auto-detect language
        sample = audio[:30 * 16000]
        inputs = processor(sample, sampling_rate=16000, return_tensors="pt")
        features = inputs.input_features.to(DEVICE, dtype=TORCH_TYPE)
        with torch.no_grad():
            ids = model.generate(features, task="transcribe", max_new_tokens=5)
        token = processor.tokenizer.convert_ids_to_tokens(ids[0][1].item())
        lang_label = _LANG_TOKEN_MAP.get(token, token.replace("<|", "").replace("|>", "").title())

    result = asr_pipe(
        audio,
        return_timestamps=True,
        chunk_length_s=30,
        stride_length_s=5,
        generate_kwargs=gen_kwargs,
    )

    return {
        "language": lang_label,
        "text": result["text"].strip(),
        "plain_text": result["text"].strip(),
        "duration_sec": duration_sec,
        "model_used": "whisper-small",
        "speakers": None,
        "has_diarization": False,
    }


# ── Main entry point ──────────────────────────────────────────────────────────
def transcribe_audio_file(audio_path: str, language: str = None) -> dict:
    """
    Smart routing:
      - Audio > 5 min  → Deepgram Nova-3 (with diarization)
      - Audio ≤ 5 min  → Whisper (local CPU)
      - Fallback to Whisper if Deepgram fails
    """
    import librosa
    # Get duration quickly
    try:
        audio, _ = librosa.load(audio_path, sr=16000, mono=True)
        duration_sec = len(audio) / 16000
    except Exception:
        duration_sec = 0

    use_deepgram = (
        duration_sec > DURATION_THRESHOLD_SEC
        and DEEPGRAM_API_KEY
    )

    if use_deepgram:
        try:
            print(f"[ASR] Duration {duration_sec:.0f}s > {DURATION_THRESHOLD_SEC}s → using Deepgram")
            return _transcribe_deepgram(audio_path, language)
        except Exception as e:
            print(f"[ASR] Deepgram failed: {e} — falling back to Whisper")
            return _transcribe_whisper(audio_path, language)
    else:
        engine = "Whisper (short audio)" if not use_deepgram and DEEPGRAM_API_KEY else "Whisper (no Deepgram key)"
        print(f"[ASR] Duration {duration_sec:.0f}s → using {engine}")
        return _transcribe_whisper(audio_path, language)


print("[ASR] Transcription service loaded (lazy model init).")
