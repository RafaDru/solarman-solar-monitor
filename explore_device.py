#!/usr/bin/env python3
"""Explorar campos disponíveis no microinversor"""

import hashlib
import json
import os
import requests

BASE_URL = "https://globalapi.solarmanpv.com"

def sha256_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()

def get_token():
    resp = requests.post(
        f"{BASE_URL}/account/v1.0/token?appId={os.getenv('SOLARMAN_APIID')}&language=en",
        headers={"Content-Type": "application/json"},
        json={
            "appSecret": os.getenv("SOLARMAN_APKKEY"),
            "email": os.getenv("SOLARMAN_EMAIL"),
            "password": sha256_hash(os.getenv("SOLARMAN_PASSWORD", "")),
        }
    )
    return resp.json()["access_token"]

def api_post(path, token, body=None):
    resp = requests.post(
        f"{BASE_URL}{path}",
        headers={"Content-Type": "application/json", "Authorization": f"bearer {token}"},
        json=body or {}
    )
    resp.raise_for_status()
    return resp.json()

token = get_token()
inv_sns = ["2209202725", "2209201606"]

for sn in inv_sns:
    print(f"\n=== MICROINVERSOR {sn} ===")
    try:
        data = api_post("/device/v1.0/currentData", token, {"deviceSn": sn})
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"Erro: {e}")

# Tentar histórico com timeType diferente
print("\n\n=== HISTÓRICO COM TIMETYPE=1 (diário) ===")
try:
    resp = api_post("/device/v1.0/historical", token, {
        "deviceSn": "2209202725",
        "timeType": 1,
        "startTime": "2026-05-07",
        "endTime": "2026-05-07"
    })
    print(json.dumps(resp, indent=2))
except Exception as e:
    print(f"Erro timeType=1: {e}")

print("\n\n=== HISTÓRICO COM TIMETYPE=2 (mensal) ===")
try:
    resp = api_post("/device/v1.0/historical", token, {
        "deviceSn": "2209202725",
        "timeType": 2,
        "startTime": "2026-01-01",
        "endTime": "2026-12-31"
    })
    print(json.dumps(resp, indent=2))
except Exception as e:
    print(f"Erro timeType=2: {e}")

print("\n\n=== HISTÓRICO COM TIMETYPE=5 (unix) - última hora ===")
from datetime import datetime
now_ts = int(datetime.now().timestamp())
try:
    resp = api_post("/device/v1.0/historical", token, {
        "deviceSn": "2209202725",
        "timeType": 5,
        "startTime": str(now_ts - 3600),
        "endTime": str(now_ts)
    })
    print(json.dumps(resp, indent=2))
except Exception as e:
    print(f"Erro timeType=5 (1h): {e}")