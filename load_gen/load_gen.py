import time
import random
import requests
import os

url = os.environ.get('TARGET_URL', 'http://web_app:5000')
endpoints = ['/', '/api/data', '/health', '/api/data', '/api/data']
print(f'Load generator started -> {url}', flush=True)

i = 0
while True:
    ep = random.choice(endpoints)
    try:
        r = requests.get(f'{url}{ep}', timeout=3)
        if i % 100 == 0:
            print(f'[{i:6d}] {ep} -> {r.status_code}', flush=True)
    except Exception as e:
        if i % 100 == 0:
            print(f'[{i:6d}] error: {e}', flush=True)
    i += 1
    time.sleep(random.uniform(0.15, 0.4))
