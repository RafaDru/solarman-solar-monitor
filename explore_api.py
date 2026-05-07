#!/usr/bin/env python3
"""Script para descobrir estrutura de dados da API SOLARMAN"""

import hashlib
import json
import os
from datetime import datetime
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

print("=== ESTAÇÕES ===")
stations = api_post("/station/v1.0/list", token, {"page": 1, "size": 10})
print(json.dumps(stations, indent=2))

st_id = stations["stationList"][0]["id"]
print(f"\n\n=== DISPOSITIVOS DA ESTAÇÃO {st_id} ===")
devices = api_post("/station/v1.0/device", token, {"page": 1, "size": 20, "stationId": st_id})
print(json.dumps(devices, indent=2))

print("\n\n=== DADOS EM TEMPO REAL (ESTAÇÃO) ===")
realtime = api_post("/station/v1.0/realTime", token, {"stationId": st_id})
print(json.dumps(realtime, indent=2))

# Testar histórico - timeType=1 (diário), dia de hoje
today = datetime.now().strftime("%Y-%m-%d")
print(f"\n\n=== HISTÓRICO DIÁRIO ({today}) ===")
try:
    hist = api_post("/station/v1.0/historical", token, {"stationId": st_id, "date": today})
    print(json.dumps(hist, indent=2))
except Exception as e:
    print(f"Erro histórico estação: {e}")

# Testar histórico do inversor - pegar primeiro inversor
inv = devices.get("deviceListItems", [])
inv_sn = None
for d in inv:
    if d.get("deviceType") == "INVERTER" or d.get("deviceType") == "MICRO_INVERTER":
        inv_sn = d.get("deviceSn")
        print(f"\n\n=== DISPOSITIVO INVERSOR: {inv_sn} ===")
        print(json.dumps(d, indent=2))
        break

if inv_sn:
    print(f"\n\n=== HISTÓRICO DO INVERSOR {inv_sn} ===")
    now_ts = int(datetime.now().timestamp())
    day_ago_ts = now_ts - 86400
    try:
        inv_hist = api_post("/device/v1.0/historical", token, {
            "deviceSn": inv_sn,
            "timeType": 5,  # Unix timestamp (5min intervals)
            "startTime": str(day_ago_ts),
            "endTime": str(now_ts)
        })
        print(f"Keys: {list(inv_hist.keys())}")
        if "datalist" in inv_hist:
            print(f"Número de registros: {len(inv_hist.get('datalist', []))}")
            if inv_hist.get("datalist"):
                print(f"Primeiro registro (campos): {list(inv_hist['datalist'][0].keys())}")
                print(f"Primeiro registro: {json.dumps(inv_hist['datalist'][0], indent=2)}")
        if "info" in inv_hist:
            print(f"Info: {json.dumps(inv_hist['info'], indent=2)}")
    except Exception as e:
        print(f"Erro histórico inversor: {e}")