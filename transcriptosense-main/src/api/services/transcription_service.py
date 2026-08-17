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
    """Lazy-init Deepgram client (Deprecated in favor of direct HTTP)"""
    pass


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


def _transcribe_deepgram(audio_path: str, language: str = None) -> dict:
    """
    Transcribe using Deepgram Nova-2 via direct HTTP request to avoid SDK versioning issues.
    ✅ Client simple et robuste.
    ✅ SSL géré globalement.
    """
    import httpx
    
    print(f"[ASR] Deepgram Nova-2: sending {audio_path}")
    
    url = "https://api.deepgram.com/v1/listen"
    params = {
        "model": "nova-2",
        "smart_format": "true",
        "diarize": "true",
        "utterances": "true",
        "paragraphs": "true",
    }
    
    if language and language.strip():
        params["language"] = language.strip()
    else:
        params["detect_language"] = "true"

    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "audio/wav"
    }

    try:
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
            
        with httpx.Client(timeout=120.0, verify=False) as client:
            resp = client.post(url, headers=headers, params=params, content=audio_bytes)
            resp.raise_for_status()
            response_data = resp.json()
            
    except Exception as e:
        print(f"[ASR] Deepgram request failed: {e}")
        raise e

    # ── Parser la réponse JSON ─────────────────────────────────
    try:
        results   = response_data.get("results", {})
        channels  = results.get("channels", [{}])
        channel   = channels[0] if channels else {}
        alts      = channel.get("alternatives", [{}])
        alt       = alts[0] if alts else {}
        full_text = alt.get("transcript", "")

        detected_lang = channel.get("detected_language", "Unknown")
        metadata      = response_data.get("metadata", {})
        duration      = metadata.get("duration", 0)

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

        utterances = results.get("utterances", [])
        if utterances:
            speaker_map      = {}
            next_speaker_num = 1
            lines            = []
            current_speaker  = None
            current_parts    = []

            for utt in utterances:
                raw_speaker = utt.get("speaker", 0)

                if raw_speaker not in speaker_map:
                    speaker_map[raw_speaker] = next_speaker_num
                    next_speaker_num += 1
                speaker_num = speaker_map[raw_speaker]

                start_time = utt.get("start", 0)
                end_time   = utt.get("end", 0)
                text       = utt.get("transcript", "").strip()

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
        full_text     = ""
        duration      = 0
        lang_label    = language or "Unknown"
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
    
    asr_pipe, processor, model = _get_whisper_pipeline()
    
    DEVICE     = "cuda" if torch.cuda.is_available() else "cpu"
    TORCH_TYPE = torch.float16 if torch.cuda.is_available() else torch.float32

    try:
        import librosa
        audio, _     = librosa.load(audio_path, sr=16000, mono=True)
        duration_sec = round(len(audio) / 16000, 2)
    except ImportError:
        # Fallback to soundfile or just raise if audio can't be loaded
        import soundfile as sf
        audio, samplerate = sf.read(audio_path)
        if samplerate != 16000:
            import numpy as np
            # Not a real resampler, but prevents crashing entirely if librosa is missing.
            # In a real app, librosa or pydub should be installed.
            audio = audio.astype(np.float32)
        duration_sec = round(len(audio) / samplerate, 2)

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


# ── Local Tunisian Model (Wav2Vec2-BERT-CTC) ──────────────────────────────
_tunisian_processor = None
_tunisian_model     = None

def _get_tunisian_pipeline():
    """Lazy-load local Tunisian ASR model."""
    import torch
    global _tunisian_processor, _tunisian_model
    if _tunisian_model is not None:
        return _tunisian_processor, _tunisian_model

    from transformers import Wav2Vec2BertProcessor, Wav2Vec2BertForCTC
    # Path to the local fine-tuned model
    MODEL_PATH = r"C:\Users\Lenovo\w2v-bert-tunisian-ctc"
    
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Tunisian model not found at {MODEL_PATH}")

    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[ASR] Loading Tunisian Local Model from {MODEL_PATH} on {DEVICE}")

    _tunisian_processor = Wav2Vec2BertProcessor.from_pretrained(MODEL_PATH)
    _tunisian_model     = Wav2Vec2BertForCTC.from_pretrained(MODEL_PATH)
    _tunisian_model.to(DEVICE)
    
    return _tunisian_processor, _tunisian_model

def _transcribe_tunisian(audio_path: str, language: str = "ar") -> dict:
    """Transcribe using the local Wav2Vec2 Tunisian model."""
    import torch
    
    processor, model = _get_tunisian_pipeline()
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

    try:
        import librosa
        audio, _     = librosa.load(audio_path, sr=16000, mono=True)
        duration_sec = round(len(audio) / 16000, 2)
    except ImportError:
        import soundfile as sf
        audio, samplerate = sf.read(audio_path)
        if samplerate != 16000:
            import numpy as np
            audio = audio.astype(np.float32)
        duration_sec = round(len(audio) / samplerate, 2)

    # Process audio
    inputs = processor(audio, sampling_rate=16000, return_tensors="pt")
    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}

    with torch.no_grad():
        logits = model(**inputs).logits
    
    predicted_ids = torch.argmax(logits, dim=-1)
    transcription = processor.batch_decode(predicted_ids)[0]

    return {
        "language":        "Arabic / Tunisian (Local)",
        "text":            transcription.strip(),
        "plain_text":      transcription.strip(),
        "diarized_text":   transcription.strip(),
        "duration_sec":    duration_sec,
        "model_used":      "w2v-bert-tunisian-ctc",
        "speakers":        None,
        "has_diarization": False,
    }


# ── Main entry point ──────────────────────────────────────────────────────────
def transcribe_audio_file(audio_path: str, language: str = None) -> dict:
    """
    Smart routing:
      - Use Local Tunisian model if Arabic/Tunisian is explicitly requested.
      - Use Deepgram Nova-2 whenever a Deepgram API key is configured.
      - Fallback to Whisper local CPU if Deepgram is unavailable or fails.
    """
    try:
        import librosa
        audio, _     = librosa.load(audio_path, sr=16000, mono=True)
        duration_sec = len(audio) / 16000
    except Exception:
        duration_sec = 0

    # Priorities: If Arabic/Darija/Tunisian is forced, try the local model first
    is_arabic = language and language.lower().strip() in ["ar", "darija", "arabic", "tunisian"]
    if is_arabic:
        try:
            print("[ASR] Arabic/Tunisian requested: Trying local Tunisian model...")
            return _transcribe_tunisian(audio_path, language)
        except Exception as e:
            print(f"[ASR] Local Tunisian model failed or not found: {e} — falling back to standard models")

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
