import time
import requests
import sys

HEALTH = 'http://127.0.0.1:8000/health'
TRANSCRIBE = 'http://127.0.0.1:8000/api/transcribe'
WAV = r"C:\Users\mbaklouti1\Downloads\i-never-said-you-were-a-superhero-didn't-well-good-because-that-would-be-outlandish-and-fantastic.wav"

# wait for health
for i in range(20):
    try:
        r = requests.get(HEALTH, timeout=2)
        if r.status_code == 200:
            print('health ok')
            break
    except Exception as e:
        print('waiting for server...', i)
        time.sleep(1)
else:
    print('server did not become ready')
    sys.exit(2)

# post file
with open(WAV, 'rb') as f:
    files = {'file': (WAV.split('\\')[-1], f, 'audio/wav')}
    data = {'language': ''}
    print('posting file...')
    r = requests.post(TRANSCRIBE, files=files, data=data, timeout=300)
    print('status', r.status_code)
    try:
        print('json:', r.json())
    except Exception:
        print('text:', r.text)
