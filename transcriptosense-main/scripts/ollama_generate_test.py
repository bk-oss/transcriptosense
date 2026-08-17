import httpx

payload={'model':'mistral:latest','prompt':'Translate "Hello, world!" to French. Return only translated text.','stream':False}
try:
    r=httpx.post('http://localhost:11434/api/generate', json=payload, timeout=60.0)
    print('status', r.status_code)
    try:
        print('json:', r.json())
    except Exception:
        print('text:', r.text)
except Exception as e:
    print('error', e)
