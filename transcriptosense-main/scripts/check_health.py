import urllib.request, traceback
url='http://127.0.0.1:8000/health'
try:
    with urllib.request.urlopen(url, timeout=5) as r:
        print('status', r.status, r.read().decode())
except Exception:
    traceback.print_exc()
