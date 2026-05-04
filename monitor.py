#!/usr/bin/env python3
"""SOLARMAN Solar Monitor - Monitoramento proativo de geração solar"""

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta
import requests

BASE_URL = "https://globalapi.solarmanpv.com"
TOKEN_URL = f"{BASE_URL}/account/v1.0/token"
STATION_LIST_URL = f"{BASE_URL}/station/v1.0/list"
REALTIME_URL = f"{BASE_URL}/station/v1.0/realtime"
HISTORICAL_URL = f"{BASE_URL}/station/v1.0/historical"

def sha256_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path, "r") as f:
        return json.load(f)

def get_token(config):
    payload = {
        "appSecret": config["appSecret"],
        "email": config["email"],
        "password": sha256_hash(config["password"])
    }
    headers = {"Content-Type": "application/json"}
    resp = requests.post(
        f"{TOKEN_URL}?appId={config['appId']}&language=en",
        headers=headers,
        json=payload
    )
    resp.raise_for_status()
    return resp.json()["access_token"]

def get_station_list(token):
    headers = {"Authorization": f"bearer {token}", "Content-Type": "application/json"}
    resp = requests.post(REALTIME_URL.replace("/realtime", "/list"), headers=headers, json={"size": 20, "page": 1})
    resp.raise_for_status()
    return resp.json().get("stationList", [])

def get_realtime_data(token, station_id):
    headers = {"Authorization": f"bearer {token}", "Content-Type": "application/json"}
    resp = requests.post(
        REALTIME_URL,
        headers=headers,
        json={"stationId": station_id}
    )
    resp.raise_for_status()
    return resp.json()

def get_historical_data(token, station_id, date):
    headers = {"Authorization": f"bearer {token}", "Content-Type": "application/json"}
    resp = requests.post(
        HISTORICAL_URL,
        headers=headers,
        json={"stationId": station_id, "date": date}
    )
    resp.raise_for_status()
    return resp.json()

def send_alert(message, config):
    if config.get("notify", {}).get("webhook_url"):
        try:
            requests.post(config["notify"]["webhook_url"], json={"text": message}, timeout=10)
        except Exception as e:
            print(f"Erro ao enviar webhook: {e}")
    if config.get("notify", {}).get("email"):
        print(f"ALERTA: {message}")

def check_generation(station_id, token, config, state_file):
    data = get_realtime_data(token, station_id)
    now = datetime.now()
    generation_power = data.get("generationPower", 0)
    last_update = data.get("lastUpdateTime", "")

    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Geração atual: {generation_power}W | Última atualização: {last_update}")

    state = {}
    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            state = json.load(f)

    last_gen_time = state.get("last_generation_time")
    alert_sent = state.get("alert_sent_24h", False)

    if generation_power and generation_power > 0:
        state["last_generation_time"] = now.isoformat()
        state["alert_sent_24h"] = False
    else:
        if last_gen_time:
            last_time = datetime.fromisoformat(last_gen_time)
            hours_without = (now - last_time).total_seconds() / 3600
            if hours_without >= 24 and not alert_sent:
                msg = f"ALERTA: Sem geração solar há {hours_without:.1f} horas na estação {station_id}!"
                print(msg)
                send_alert(msg, config)
                state["alert_sent_24h"] = True
        else:
            state["last_generation_time"] = now.isoformat()

    with open(state_file, "w") as f:
        json.dump(state, f)

def main():
    config = load_config()
    state_file = os.path.join(os.path.dirname(__file__), "state.json")

    token = get_token(config)
    stations = get_station_list(token)

    if not stations:
        print("Nenhuma estação encontrada.")
        return

    station_id = stations[0]["id"]
    print(f"Monitorando estação ID: {station_id}")

    check_generation(station_id, token, config, state_file)

if __name__ == "__main__":
    main()
