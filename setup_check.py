"""
TranscriptoSense — Environment Health Check
Run this after installing requirements to verify everything is ready.

Usage:
    python setup_check.py
    python setup_check.py --verbose
"""

import sys
import importlib
import subprocess
import argparse
from pathlib import Path

# ── Terminal colors (no external deps) ──────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):    print(f"  {GREEN}✓{RESET} {msg}")
def warn(msg):  print(f"  {YELLOW}⚠{RESET} {msg}")
def fail(msg):  print(f"  {RED}✗{RESET} {msg}")
def info(msg):  print(f"  {BLUE}→{RESET} {msg}")
def header(msg):print(f"\n{BOLD}{msg}{RESET}")


def check_python():
    header("Python Version")
    v = sys.version_info
    if v.major == 3 and v.minor >= 9:
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        fail(f"Python {v.major}.{v.minor} — need 3.9+")


def check_import(package_name, import_name=None, min_version=None, tier="bronze"):
    import_name = import_name or package_name
    tier_badge = {"bronze": "🥉", "silver": "🥈", "gold": "🥇", "util": "  "}.get(tier, "")
    try:
        mod = importlib.import_module(import_name)
        version = getattr(mod, "__version__", "?")
        ok(f"{tier_badge} {package_name} {version}")
        return True
    except ImportError:
        if tier == "bronze":
            fail(f"{tier_badge} {package_name} — NOT FOUND (required for Bronze)")
        else:
            warn(f"{tier_badge} {package_name} — not installed ({tier} tier)")
        return False


def check_torch():
    header("PyTorch & CUDA")
    try:
        import torch
        ok(f"torch {torch.__version__}")
        if torch.cuda.is_available():
            ok(f"CUDA available — device: {torch.cuda.get_device_name(0)}")
        else:
            warn("CUDA not available — running on CPU (use Colab for GPU)")
        return True
    except ImportError:
        fail("torch — NOT FOUND")
        return False


def check_faster_whisper():
    header("ASR — faster-whisper")
    try:
        from faster_whisper import WhisperModel
        ok("faster-whisper importable")
        info("To test: WhisperModel('tiny', device='cpu', compute_type='int8')")
        return True
    except ImportError:
        fail("faster-whisper — NOT FOUND  →  pip install faster-whisper")
        return False


def check_pyannote():
    header("Diarization — pyannote.audio (Silver tier)")
    try:
        import pyannote.audio
        ok(f"pyannote.audio {pyannote.audio.__version__}")
        # Check for HF token
        from dotenv import load_dotenv
        import os
        load_dotenv()
        token = os.getenv("HUGGINGFACE_TOKEN", "")
        if token and token != "hf_YOUR_TOKEN_HERE":
            ok("HUGGINGFACE_TOKEN found in .env")
        else:
            warn("HUGGINGFACE_TOKEN not set — diarization won't load model")
            info("Set it in .env (copy .env.example → .env)")
        return True
    except ImportError:
        warn("pyannote.audio — not installed (needed for Silver tier)")
        return False


def check_spacy():
    header("NLP — spaCy")
    try:
        import spacy
        ok(f"spacy {spacy.__version__}")
        try:
            nlp = spacy.load("fr_core_news_sm")
            ok("fr_core_news_sm model loaded")
        except OSError:
            warn("fr_core_news_sm not downloaded")
            info("Run: python -m spacy download fr_core_news_sm")
        return True
    except ImportError:
        fail("spacy — NOT FOUND")
        return False


def check_ffmpeg():
    header("System — ffmpeg")
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True
        )
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0]
            ok(f"ffmpeg found — {version_line[:60]}")
        else:
            fail("ffmpeg returned non-zero exit code")
    except FileNotFoundError:
        fail("ffmpeg — NOT FOUND (needed for audio format conversion)")
        info("Install: https://ffmpeg.org/download.html")
        info("On Ubuntu/Debian: sudo apt install ffmpeg")
        info("On Windows: winget install ffmpeg")


def check_env_file():
    header("Configuration")
    env_path = Path(".env")
    example_path = Path(".env.example")
    if env_path.exists():
        ok(".env file found")
    else:
        warn(".env file missing")
        if example_path.exists():
            info("Run: cp .env.example .env  then fill in your HuggingFace token")
        else:
            warn(".env.example also missing")

    config_path = Path("config.py")
    if config_path.exists():
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent))
            from config import CFG
            ok(f"config.py loads OK — ASR model: {CFG.asr['model_size']}")
        except Exception as e:
            fail(f"config.py failed to import: {e}")
    else:
        fail("config.py not found")


def check_dirs():
    header("Project Directories")
    expected = [
        "data/raw", "data/processed", "data/annotations",
        "src/ingestion", "src/asr", "src/diarization",
        "src/nlp", "src/synthesis", "src/api", "src/ui",
        "models", "outputs/transcripts", "outputs/summaries", "outputs/exports",
        "notebooks", "tests",
    ]
    all_ok = True
    for d in expected:
        p = Path(d)
        if p.exists():
            ok(str(p))
        else:
            warn(f"{d} — missing (will be created by config.py)")
            all_ok = False
    return all_ok


def print_summary(results: dict):
    header("=" * 50)
    header("Summary")
    total = len(results)
    passed = sum(results.values())
    failed = total - passed
    if failed == 0:
        print(f"\n  {GREEN}{BOLD}All {total} checks passed. You're ready to code! 🚀{RESET}")
    else:
        print(f"\n  {GREEN}✓ {passed} passed{RESET}  |  {RED}✗ {failed} need attention{RESET}")
        print(f"\n  Failing checks:")
        for name, ok_ in results.items():
            if not ok_:
                print(f"    {RED}✗{RESET} {name}")
    print()


def main():
    parser = argparse.ArgumentParser(description="TranscriptoSense environment check")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    print(f"\n{BOLD}{'='*50}")
    print("  TranscriptoSense — Environment Check")
    print(f"{'='*50}{RESET}")

    results = {}

    check_python()

    header("Core Libraries")
    results["numpy"]        = check_import("numpy", tier="bronze")
    results["pandas"]       = check_import("pandas", tier="bronze")
    results["torch"]        = check_torch()
    results["scipy"]        = check_import("scipy", tier="bronze")
    results["scikit-learn"] = check_import("sklearn", "sklearn", tier="bronze")
    results["tqdm"]         = check_import("tqdm", tier="util")
    results["loguru"]       = check_import("loguru", tier="util")
    results["dotenv"]       = check_import("python-dotenv", "dotenv", tier="util")

    header("Audio Libraries")
    results["soundfile"]    = check_import("soundfile", tier="bronze")
    results["librosa"]      = check_import("librosa", tier="bronze")
    results["pydub"]        = check_import("pydub", tier="bronze")
    results["webrtcvad"]    = check_import("webrtcvad", tier="bronze")

    results["faster-whisper"] = check_faster_whisper()

    check_pyannote()     # Silver — not in required results

    header("NLP Libraries")
    results["transformers"] = check_import("transformers", tier="silver")
    results["sentence-transformers"] = check_import(
        "sentence-transformers", "sentence_transformers", tier="silver")
    results["keybert"]      = check_import("keybert", tier="silver")
    results["langdetect"]   = check_import("langdetect", tier="bronze")
    results["ftfy"]         = check_import("ftfy", tier="bronze")
    check_spacy()

    header("Evaluation")
    results["jiwer"]        = check_import("jiwer", tier="bronze")
    results["rouge-score"]  = check_import("rouge-score", "rouge_score", tier="bronze")
    results["bert-score"]   = check_import("bert-score", "bert_score", tier="silver")

    header("API / UI")
    results["fastapi"]      = check_import("fastapi", tier="bronze")
    results["uvicorn"]      = check_import("uvicorn", tier="bronze")
    results["streamlit"]    = check_import("streamlit", tier="bronze")
    results["gradio"]       = check_import("gradio", tier="silver")

    header("Export")
    results["python-docx"]  = check_import("python-docx", "docx", tier="bronze")
    results["reportlab"]    = check_import("reportlab", tier="bronze")

    check_ffmpeg()
    check_env_file()
    check_dirs()

    print_summary(results)


if __name__ == "__main__":
    main()
