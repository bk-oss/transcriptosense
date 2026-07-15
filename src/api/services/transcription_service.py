import os
import torch
import librosa
from pathlib import Path
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

# ── Model Resolution ──────────────────────────────────────────────────────────
# Priority: WHISPER_MODEL_ID env var → local models/ folder → HuggingFace Hub
_BASE_DIR     = Path(__file__).resolve().parent.parent.parent.parent
_LOCAL_MODEL  = _BASE_DIR / "models" / "whisper-large-v3"
MODEL_ID      = os.getenv(
    "WHISPER_MODEL_ID",
    str(_LOCAL_MODEL) if _LOCAL_MODEL.exists() else "openai/whisper-large-v3"
)

DEVICE      = "cuda" if torch.cuda.is_available() else "cpu"
TORCH_TYPE  = torch.float16 if torch.cuda.is_available() else torch.float32

print(f"[ASR] Loading model  : {MODEL_ID}")
print(f"[ASR] Device         : {DEVICE}")

processor = AutoProcessor.from_pretrained(MODEL_ID)

model = AutoModelForSpeechSeq2Seq.from_pretrained(
    MODEL_ID,
    torch_dtype=TORCH_TYPE,
    low_cpu_mem_usage=True,
    use_safetensors=True,
)
model.to(DEVICE)

asr_pipeline = pipeline(
    task="automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    torch_dtype=TORCH_TYPE,
    device=DEVICE,
)

print("[ASR] Pipeline ready.")

# ── Language token → human-readable label ─────────────────────────────────────
_LANG_TOKEN_MAP = {
    "<|fr|>": "French",    "<|ar|>": "Arabic",   "<|en|>": "English",
    "<|es|>": "Spanish",   "<|de|>": "German",   "<|it|>": "Italian",
    "<|pt|>": "Portuguese","<|nl|>": "Dutch",     "<|zh|>": "Chinese",
    "<|ja|>": "Japanese",  "<|ko|>": "Korean",    "<|ru|>": "Russian",
    "<|tr|>": "Turkish",
}

_USER_LANG_LABELS = {
    "fr": "French",
    "ar": "Arabic / Tunisian",
    "en": "English",
}


def _detect_language(audio_np) -> str:
    """Auto-detect language from first 30 s of audio via Whisper's language token."""
    sample   = audio_np[:30 * 16000]
    inputs   = processor(sample, sampling_rate=16000, return_tensors="pt")
    features = inputs.input_features.to(DEVICE, dtype=TORCH_TYPE)
    with torch.no_grad():
        ids = model.generate(features, task="transcribe", max_new_tokens=5)
    token = processor.tokenizer.convert_ids_to_tokens(ids[0][1].item())
    return _LANG_TOKEN_MAP.get(token, token.replace("<|", "").replace("|>", "").title())


def transcribe_audio_file(audio_path: str, language: str = None) -> dict:
    """
    Transcribe an audio file.

    Args:
        audio_path: Path to the audio file.
        language:   ISO-639-1 code ("fr", "ar", …) or None for auto-detect.

    Returns:
        {"language": str, "text": str, "duration_sec": float}
    """
    audio, _ = librosa.load(audio_path, sr=16000, mono=True)
    duration_sec = round(len(audio) / 16000, 2)

    gen_kwargs: dict = {"task": "transcribe"}

    if language:
        gen_kwargs["language"] = language
        lang_label = _USER_LANG_LABELS.get(language, language.title())
    else:
        lang_label = _detect_language(audio)

    result = asr_pipeline(
        audio,
        return_timestamps=True,
        chunk_length_s=30,
        stride_length_s=5,
        generate_kwargs=gen_kwargs,
    )

    return {
        "language":    lang_label,
        "text":        result["text"].strip(),
        "duration_sec": duration_sec,
    }
