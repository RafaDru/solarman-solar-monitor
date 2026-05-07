import json, os, requests, hashlib

BASE_URL = 'https://globalapi.solarmanpv.com'
def sha256_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()

resp = requests.post(
    f'{BASE_URL}/account/v1.0/token?appId={os.getenv("SOLARMAN_APIID")}&language=en',
    headers={'Content-Type': 'application/json'},
    json={
        'appSecret': os.getenv('SOLARMAN_APKKEY'),
        'email': os.getenv('SOLARMAN_EMAIL'),
        'password': sha256_hash(os.getenv('SOLARMAN_PASSWORD', '')),
    }
)
token = resp.json()['access_token']

resp = requests.post(
    f'{BASE_URL}/device/v1.0/currentData',
    headers={'Content-Type': 'application/json', 'Authorization': f'bearer {token}'},
    json={'deviceSn': '2209201606'}
)
data = resp.json()
print('=== currentData - todos campos (inversor 2209201606) ===')
for item in data.get('dataList', []):
    print(f'  {item["key"]}: {item["value"]} {item.get("unit","") or ""} ({item["name"]})')

print('\n=== currentData - todos campos (inversor 2209202725) ===')
resp = requests.post(
    f'{BASE_URL}/device/v1.0/currentData',
    headers={'Content-Type': 'application/json', 'Authorization': f'bearer {token}'},
    json={'deviceSn': '2209202725'}
)
data = resp.json()
for item in data.get('dataList', []):
    print(f'  {item["key"]}: {item["value"]} {item.get("unit","") or ""} ({item["name"]})')