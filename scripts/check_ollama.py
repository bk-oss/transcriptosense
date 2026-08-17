import httpx

base='http://localhost:11434'
print('Checking', base)
try:
    r = httpx.get(base+'/api/tags', timeout=5.0)
    print('/api/tags', r.status_code)
    try:
        data = r.json()
        print('models:', [m.get('name') for m in data.get('models', []) if isinstance(m, dict)])
    except Exception as e:
        print('tags json error', e)
except Exception as e:
    print('/api/tags error:', repr(e))

# Try a small generate if tags ok
try:
    payload={'model':'mistral:latest','prompt':'Translate "Hello" to French. Return only translated text.','stream':False}
    r2 = httpx.post(base+'/api/generate', json=payload, timeout=20.0)
    print('/api/generate', r2.status_code)
    try:
        print('response json keys:', list(r2.json().keys()))
        print('response:', r2.json().get('response'))
    except Exception as e:
        print('generate json err', e)
except Exception as e:
    print('/api/generate error:', repr(e))
