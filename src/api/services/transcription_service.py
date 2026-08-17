"""
TranscriptoSense — Transcription Service

Smart routing:
  - Audio > 5 minutes  → Deepgram Nova-2 (cloud, with diarization)
  - Audio ≤ 5 minutes  → Whisper small (local CPU)
  - Fallback: if Deepgram fails → Whisper
"""

import os
import ssl

# ══════════════════════════════════════════════════════════════════════════
# ✅ SSL FIX — proxy entreprise, doit être avant tous les autres imports
# ══════════════════════════════════════════════════════════════════════════
os.environ["PYTHONHTTPSVERIFY"]  = "0"
os.environ["CURL_CA_BUNDLE"]     = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""
ssl._create_default_https_context = ssl._create_unverified_context

import json
from pathlib import Path
from dotenv import load_dotenv

# ── Charger .env EN PREMIER, avant tout ──────────────────────────────────────
load_dotenv(
    dotenv_path=Path(__file__).resolve().parent.parent.parent.parent / ".env",
    override=True,
)

# ── Thresholds ────────────────────────────────────────────────────────────────
DURATION_THRESHOLD_SEC = 5 * 60  # 5 minutes

# ── Deepgram setup ────────────────────────────────────────────────────────────
DEEPGRAM_API_KEY = (
    os.getenv("DEEPGRAM_API_KEY")
    or os.getenv("DEEPGRAM_KEY")
    or os.getenv("DEEPGRAM_NOVA_KEY")
    or os.getenv("DEEPGRAM_NOVA_API_KEY")
    or ""
)

if DEEPGRAM_API_KEY:
    print(f"[ASR] Deepgram key loaded: {DEEPGRAM_API_KEY[:6]}...{DEEPGRAM_API_KEY[-4:]}")
else:
    print("[ASR] WARNING: No Deepgram key found!")

_deepgram_client = None


def _get_deepgram_client():
    """Lazy-init Deepgram client — compatible v7.6.0"""
    global _deepgram_client
    if _deepgram_client is None and DEEPGRAM_API_KEY:
        from deepgram import DeepgramClient
        _deepgram_client = DeepgramClient(api_key=DEEPGRAM_API_KEY)
        print("[ASR] Deepgram client initialized.")
    return _deepgram_client


# ── Whisper setup (lazy load) ─────────────────────────────────────────────────
_whisper_pipeline  = None
_whisper_processor = None
_whisper_model     = None

def _get_whisper_pipeline():
    """Lazy-load Whisper model only when needed."""
    import torch
    global _whisper_pipeline, _whisper_processor, _whisper_model
    if _whisper_pipeline is not None:
        return _whisper_pipeline, _whisper_processor, _whisper_model

    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

    _BASE_DIR    = Path(__file__).resolve().parent.parent.parent.parent
    _LOCAL_MODEL = _BASE_DIR / "models" / "whisper-small"
    MODEL_ID = os.getenv(
        "WHISPER_MODEL_ID",
        str(_LOCAL_MODEL) if _LOCAL_MODEL.exists() else "openai/whisper-small"
    )

    DEVICE     = "cuda" if torch.cuda.is_available() else "cpu"
    TORCH_TYPE = torch.float16 if torch.cuda.is_available() else torch.float32

    print(f"[ASR] Loading Whisper: {MODEL_ID} on {DEVICE}")

    _whisper_processor = AutoProcessor.from_pretrained(MODEL_ID)
    _whisper_model     = AutoModelForSpeechSeq2Seq.from_pretrained(
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
    "<|fr|>": "French",     "<|ar|>": "Arabic",    "<|en|>": "English",
    "<|es|>": "Spanish",    "<|de|>": "German",    "<|it|>": "Italian",
    "<|pt|>": "Portuguese", "<|nl|>": "Dutch",     "<|zh|>": "Chinese",
    "<|ja|>": "Japanese",   "<|ko|>": "Korean",    "<|ru|>": "Russian",
    "<|tr|>": "Turkish",
}

_USER_LANG_LABELS = {
    "fr": "French",
    "ar": "Arabic / Tunisian",
    "en": "English",
}

_LANG_CODE_MAP = {
    "fr": "French",     "ar": "Arabic",    "en": "English",
    "es": "Spanish",    "de": "German",    "it": "Italian",
    "pt": "Portuguese", "nl": "Dutch",     "zh": "Chinese",
    "ja": "Japanese",   "ko": "Korean",    "ru": "Russian",
    "tr": "Turkish",
}


# ── Deepgram transcription ────────────────────────────────────────────────────
def _transcribe_deepgram(audio_path: str, language: str = None) -> dict:
    """
    Transcribe using Deepgram Nova-2.
    ✅ Client simple — compatible deepgram-sdk v7.6.0
    ✅ SSL déjà géré globalement en haut du fichier
    """
    from deepgram import DeepgramClient

    client = DeepgramClient(api_key=DEEPGRAM_API_KEY)

    # ✅ request doit être bytes directement
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    # ✅ Tous les paramètres sont des kwargs nommés
    kwargs = {
        "request":      audio_bytes,
        "model":        "nova-2",
        "smart_format": True,
        "diarize":      True,
        "utterances":   True,
        "paragraphs":   True,
    }

    if language and language.strip():
        kwargs["language"] = language
    else:
        kwargs["detect_language"] = True

    print(f"[ASR] Deepgram Nova-2: sending {audio_path}")

    response = client.listen.v1.media.transcribe_file(**kwargs)

    # ── Parser la réponse (ListenV1Response) ─────────────────────────────────
    try:
        results   = response.results
        channels  = results.channels or []
        channel   = channels[0] if channels else None
        alts      = channel.alternatives if channel else []
        alt       = alts[0] if alts else None
        full_text = alt.transcript if alt else ""

        detected_lang = getattr(channel, "detected_language", None) or "Unknown"
        metadata      = response.metadata
        duration      = getattr(metadata, "duration", 0) or 0

        if language:
            lang_label = _USER_LANG_LABELS.get(language, language.title())
        else:
            lang_label = _LANG_CODE_MAP.get(
                detected_lang,
                detected_lang.title() if isinstance(detected_lang, str) else "Unknown"
            )

        # ── Diarisation depuis utterances ─────────────────────────────────────
        speakers_data = []
        diarized_text = full_text

        utterances = getattr(results, "utterances", None) or []
        if utterances:
            speaker_map      = {}
            next_speaker_num = 1
            lines            = []
            current_speaker  = None
            current_parts    = []

            for utt in utterances:
                raw_speaker = getattr(utt, "speaker", 0)

                if raw_speaker not in speaker_map:
                    speaker_map[raw_speaker] = next_speaker_num
                    next_speaker_num += 1
                speaker_num = speaker_map[raw_speaker]

                start_time = getattr(utt, "start", 0)
                end_time   = getattr(utt, "end", 0)
                text       = getattr(utt, "transcript", "").strip()

                speakers_data.append({
                    "speaker": speaker_num,
                    "start":   start_time,
                    "end":     end_time,
                    "text":    text,
                })

                if speaker_num == current_speaker:
                    current_parts.append(text)
                else:
                    if current_speaker is not None:
                        lines.append(f"Speaker {current_speaker}: {' '.join(current_parts)}")
                    current_speaker = speaker_num
                    current_parts   = [text]

            if current_speaker is not None:
                lines.append(f"Speaker {current_speaker}: {' '.join(current_parts)}")

            diarized_text = "\n".join(lines)

    except Exception as parse_err:
        print(f"[ASR] Warning: could not parse Deepgram response: {parse_err}")
        try:
            rd            = response.dict() if hasattr(response, "dict") else {}
            results       = rd.get("results", {})
            channels      = results.get("channels", [{}])
            channel       = channels[0] if channels else {}
            alts          = channel.get("alternatives", [{}])
            alt           = alts[0] if alts else {}
            full_text     = alt.get("transcript", "")
            duration      = rd.get("metadata", {}).get("duration", 0)
            lang_label    = language or "Unknown"
            diarized_text = full_text
            speakers_data = []
        except Exception:
            full_text     = ""
            duration      = 0
            lang_label    = "Unknown"
            diarized_text = ""
            speakers_data = []

    print(f"[ASR] Deepgram OK — lang={lang_label}, chars={len(full_text)}, speakers={len(speakers_data)}")

    return {
        "language":        lang_label,
        "text":            full_text.strip(),
        "plain_text":      full_text.strip(),
        "diarized_text":   diarized_text.strip(),
        "duration_sec":    round(float(duration), 2),
        "model_used":      "deepgram-nova-2",
        "speakers":        json.dumps(speakers_data) if speakers_data else None,
        "has_diarization": bool(speakers_data),
    }


# ── Whisper transcription ─────────────────────────────────────────────────────
def _transcribe_whisper(audio_path: str, language: str = None) -> dict:
    """Transcribe using local Whisper model."""
    import torch
    import librosa

    asr_pipe, processor, model = _get_whisper_pipeline()

    DEVICE     = "cuda" if torch.cuda.is_available() else "cpu"
    TORCH_TYPE = torch.float16 if torch.cuda.is_available() else torch.float32

    audio, _     = librosa.load(audio_path, sr=16000, mono=True)
    duration_sec = round(len(audio) / 16000, 2)

    gen_kwargs = {"task": "transcribe"}

    if language:
        gen_kwargs["language"] = language
        lang_label = _USER_LANG_LABELS.get(language, language.title())
    else:
        sample   = audio[:30 * 16000]
        inputs   = processor(sample, sampling_rate=16000, return_tensors="pt")
        features = inputs.input_features.to(DEVICE, dtype=TORCH_TYPE)
        with torch.no_grad():
            ids = model.generate(features, task="transcribe", max_new_tokens=5)
        token     = processor.tokenizer.convert_ids_to_tokens(ids[0][1].item())
        lang_code = token.replace("<|", "").replace("|>", "") if isinstance(token, str) else ""
        lang_label = _LANG_TOKEN_MAP.get(token)
        if not lang_label:
            lang_label = _USER_LANG_LABELS.get(lang_code)
        if not lang_label:
            lang_label = lang_code.upper() if lang_code.isalpha() else "Unknown"

    result = asr_pipe(
        audio,
        return_timestamps=True,
        chunk_length_s=30,
        stride_length_s=5,
        generate_kwargs=gen_kwargs,
    )

    return {
        "language":        lang_label,
        "text":            result["text"].strip(),
        "plain_text":      result["text"].strip(),
        "diarized_text":   result["text"].strip(),
        "duration_sec":    duration_sec,
        "model_used":      "whisper-small",
        "speakers":        None,
        "has_diarization": False,
    }


# ── Main entry point ──────────────────────────────────────────────────────────
def transcribe_audio_file(audio_path: str, language: str = None) -> dict:
    """
    Smart routing:
      - Use Deepgram Nova-2 whenever a Deepgram API key is configured.
      - Fallback to Whisper local CPU if Deepgram is unavailable or fails.
    """
    import librosa

    try:
        audio, _     = librosa.load(audio_path, sr=16000, mono=True)
        duration_sec = len(audio) / 16000
    except Exception:
        duration_sec = 0

    use_deepgram = bool(DEEPGRAM_API_KEY)

    if use_deepgram:
        try:
            print("[ASR] Using Deepgram Nova-2 for transcription")
            return _transcribe_deepgram(audio_path, language)
        except Exception as e:
            print(f"[ASR] Deepgram failed: {e} — falling back to Whisper")
            return _transcribe_whisper(audio_path, language)
    else:
        print("[ASR] Using Whisper (no Deepgram key)")
        return _transcribe_whisper(audio_path, language)


print("[ASR] Transcription service loaded (lazy model init).")
