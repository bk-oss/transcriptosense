import torch
import librosa
import time
import os
import datetime
from pathlib import Path
from transformers import WhisperProcessor, WhisperForConditionalGeneration
from config import CFG

# --- Config ---
# Use config module for portable paths instead of hardcoded user paths
LANGUAGE   = os.getenv("TRANSCRIBE_LANGUAGE", "ar")
TASK       = os.getenv("TRANSCRIBE_TASK", "transcribe")

# Get model path from config or use default
BASE_DIR = CFG.BASE_DIR if hasattr(CFG, 'BASE_DIR') else Path(__file__).parent
MODELS_DIR = getattr(CFG, 'MODELS_DIR', BASE_DIR / "models")
DATA_INTERIM = getattr(CFG, 'DATA_PROCESSED', BASE_DIR / "data" / "interim")
OUTPUT_DIR = str(getattr(CFG, 'OUT_TRANSCRIPTS', BASE_DIR / "outputs" / "transcripts"))

# Auto-detect model path
MODEL_PATH = os.getenv(
    "WHISPER_MODEL_PATH",
    str(MODELS_DIR / "whisper-large-v3")
)
AUDIO_PATH = os.getenv(
    "AUDIO_FILE_PATH",
    str(DATA_INTERIM / "meeting_16k_mono.wav")
)

os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Device ---
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Device        : {DEVICE}")
if DEVICE == "cuda":
    print(f"GPU           : {torch.cuda.get_device_name(0)}")
    vram = torch.cuda.get_device_properties(0).total_memory / 1e9
    print(f"VRAM totale   : {vram:.1f} GB")

# --- Chargement modele ---
print("\nChargement du modele Whisper Large V3...")
t0 = time.time()
processor = WhisperProcessor.from_pretrained(MODEL_PATH)
model = WhisperForConditionalGeneration.from_pretrained(
    MODEL_PATH,
    torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32,
).to(DEVICE)
model.eval()
print(f"Modele charge en {time.time()-t0:.1f}s")

# --- Chargement audio ---
print(f"\nChargement audio : {AUDIO_PATH}")
audio, sr = librosa.load(AUDIO_PATH, sr=16000, mono=True)
duration  = len(audio) / sr
print(f"Audio charge : {duration:.1f}s ({duration/60:.1f} min)")

# --- Transcription par chunks ---
CHUNK_SEC     = 30
CHUNK_SAMPLES = CHUNK_SEC * 16000

print(f"\nTranscription en cours (chunks de {CHUNK_SEC}s)...")
print(f"Langue : {LANGUAGE} | Tache : {TASK}")
print("-" * 50)

t0             = time.time()
transcriptions = []
n_chunks       = (len(audio) + CHUNK_SAMPLES - 1) // CHUNK_SAMPLES

for i in range(n_chunks):
    start = i * CHUNK_SAMPLES
    end   = min(start + CHUNK_SAMPLES, len(audio))
    chunk = audio[start:end]

    print(f"  Chunk {i+1}/{n_chunks} [{start//16000:.0f}s -> {end//16000:.0f}s]...", end=" ")

    inputs = processor(
        chunk,
        sampling_rate=16000,
        return_tensors="pt"
    ).input_features.to(DEVICE)

    with torch.no_grad():
        predicted_ids = model.generate(
            inputs,
            language=LANGUAGE,
            task=TASK,
            forced_decoder_ids=None,
        )

    chunk_text = processor.batch_decode(
        predicted_ids,
        skip_special_tokens=True
    )[0].strip()

    transcriptions.append(chunk_text)
    print(f"OK : '{chunk_text[:60]}{'...' if len(chunk_text)>60 else ''}'")

elapsed   = time.time() - t0
full_text = " ".join(transcriptions)
rtf       = elapsed / duration

# --- Affichage ---
print("\n" + "=" * 50)
print("TRANSCRIPTION COMPLETE :")
print("=" * 50)
print(full_text)
print("=" * 50)
print(f"\nTemps de traitement : {elapsed:.1f}s")
print(f"Duree audio         : {duration:.1f}s")
print(f"RTF                 : {rtf:.2f}x")

# --- Sauvegarde ---
timestamp   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = os.path.join(OUTPUT_DIR, f"transcription_{timestamp}.txt")

with open(output_file, "w", encoding="utf-8") as f:
    f.write(f"Fichier audio    : {AUDIO_PATH}\n")
    f.write(f"Modele           : Whisper Large V3\n")
    f.write(f"Langue           : {LANGUAGE}\n")
    f.write(f"Date             : {datetime.datetime.now()}\n")
    f.write(f"Duree audio      : {duration:.1f}s\n")
    f.write(f"Temps traitement : {elapsed:.1f}s\n")
    f.write(f"RTF              : {rtf:.2f}x\n")
    f.write("\n" + "=" * 50 + "\n")
    f.write("TRANSCRIPTION :\n")
    f.write("=" * 50 + "\n")
    f.write(full_text)

print(f"\nResultat sauvegarde : {output_file}")
print("TERMINE !")
