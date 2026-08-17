import requests
r = requests.post('http://127.0.0.1:8000/api/translate', json={'text':'Hello, world!','target':'fr'})
print(r.status_code)
print(r.json())
