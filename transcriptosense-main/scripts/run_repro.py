import sys
import traceback
import os
sys.path.insert(0, os.getcwd())

from src.api.services.transcription_service import transcribe_audio_file

path = r"C:\Users\mbaklouti1\Downloads\i-never-said-you-were-a-superhero-didn't-well-good-because-that-would-be-outlandish-and-fantastic.wav"
print('path', path)
try:
    result = transcribe_audio_file(path)
    print('Result:', result)
except Exception:
    traceback.print_exc()
