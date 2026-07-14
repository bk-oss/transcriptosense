import torch
import librosa
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

MODEL_PATH = r"C:\Users\mbaklouti1\Desktop\transcriptosense\models\whisper-large-v3"

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
TORCH_TYPE = torch.float16 if torch.cuda.is_available() else torch.float32

processor = AutoProcessor.from_pretrained(MODEL_PATH)

model = AutoModelForSpeechSeq2Seq.from_pretrained(
    MODEL_PATH,
    dtype=TORCH_TYPE,           # ← changed from torch_dtype
    low_cpu_mem_usage=True,
    use_safetensors=True,
)
model.to(DEVICE)

asr_pipeline = pipeline(
    task="automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    dtype=TORCH_TYPE,           # ← changed from torch_dtype
    device=DEVICE,
    generate_kwargs={"task": "transcribe"},
)


def detect_language(audio):
    sample_audio = audio[:30 * 16000]
    inputs = processor(sample_audio, sampling_rate=16000, return_tensors="pt")
    input_features = inputs.input_features.to(DEVICE, dtype=TORCH_TYPE)

    with torch.no_grad():
        predicted_ids = model.generate(input_features, task="transcribe")

    lang_token = processor.tokenizer.convert_ids_to_tokens(predicted_ids[0][1].item())
    return lang_token


def transcribe_audio_file(audio_path: str) -> dict:
    audio, sr = librosa.load(audio_path, sr=16000, mono=True)

    language = detect_language(audio)

    result = asr_pipeline(
        audio,
        return_timestamps=True,
        chunk_length_s=30,
        stride_length_s=5,
        generate_kwargs={"task": "transcribe"},
    )

    return {
        "language": language,
        "text": result["text"]
    }
