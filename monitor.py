#!/usr/bin/env python3
"""SOLARMAN Solar Monitor - Monitoramento proativo de geração solar via API v1.1.6"""

import hashlib
import json
import os
from datetime import datetime
import requests

BASE_URL = "https://globalapi.solarmanpv.com"

ENV_MAP = {
    "appId": "SOLARMAN_APIKEY",
    "appSecret": "SOLARMAN_APKKEY",
    "email": "SOLARMAN_EMAIL",
    "password": "SOLARMAN_PASSWORD",
}


def sha256_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()


def load_config():
    config = {}
    for key, env_var in ENV_MAP.items():
        value = os.getenv(env_var)
        if not value:
            raise SystemExit(
                f"Erro: variável de ambiente {env_var} não definida.\n"
                "Defina-a com:\n"
                f'  $env:{env_var} = "seu_valor"  (PowerShell)\n'
                "Ou copie .env.sample para .env e use python-dotenv."
            )
        config[key] = value
    return config


def api_post(path, token=None, body=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"bearer {token}"
    url = f"{BASE_URL}{path}"
    resp = requests.post(url, headers=headers, json=body or {})
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        print(f"  Erro HTTP {resp.status_code}: {resp.text}")
        raise
    return resp.json()


def get_token(config):
    body = {
        "appSecret": config["appSecret"],
        "email": config["email"],
        "password": sha256_hash(config["password"]),
    }
    data = api_post(f"/account/v1.0/token?appId={config['appId']}&language=en", body=body)
    return data["access_token"]


def get_station_list(token):
    data = api_post("/station/v1.0/list", token=token, body={"page": 1, "size": 20})
    return data.get("stationList", [])


def get_realtime_data(token, station_id):
    return api_post("/station/v1.0/realTime", token=token, body={"stationId": station_id})


def send_alert(message):
    webhook = os.getenv("SOLARMAN_WEBHOOK")
    if webhook:
        try:
            requests.post(webhook, json={"text": message}, timeout=10)
        except Exception as e:
            print(f"  Erro ao enviar webhook: {e}")
    print(f"\n  >>> ALERTA: {message}\n")


def check_generation(station_id, token, state_file):
    data = get_realtime_data(token, station_id)
    now = datetime.now()

    gen_power = data.get("generationPower", 0)
    last_update_ts = data.get("lastUpdateTime")

    if last_update_ts:
        last_update = datetime.fromtimestamp(float(last_update_ts))
        last_update_str = last_update.strftime("%Y-%m-%d %H:%M:%S")
    else:
        last_update_str = "N/A"

    print(f"  Geração atual: {gen_power}W")
    print(f"  Última atualização: {last_update_str}")

    state = {}
    if os.path.exists(state_file):
        with open(state_file) as f:
            state = json.load(f)

    last_gen_time = state.get("last_generation_time")
    alert_sent = state.get("alert_sent_24h", False)

    try:
        gen_val = float(gen_power) if gen_power is not None else 0
    except (ValueError, TypeError):
        gen_val = 0

    if gen_val > 0:
        state["last_generation_time"] = now.isoformat()
        state["alert_sent_24h"] = False
        print("  Status: Gerando energia OK")
    else:
        if last_gen_time:
            last_time = datetime.fromisoformat(last_gen_time)
            hours = (now - last_time).total_seconds() / 3600
            print(f"  Status: Sem geração há {hours:.1f}h")
            if hours >= 24 and not alert_sent:
                msg = (
                    f"Sem geração solar há {hours:.1f} horas "
                    f"(estação {station_id})!"
                )
                send_alert(msg)
                state["alert_sent_24h"] = True
        else:
            state["last_generation_time"] = now.isoformat()
            print("  Status: Primeira execução - monitoramento iniciado")

    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)


def main():
    config = load_config()
    state_file = os.path.join(os.path.dirname(__file__), "state.json")

    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] SOLARMAN Monitor")
    print(f"  Autenticando...")
    token = get_token(config)
    print(f"  Token obtido com sucesso")

    print(f"  Buscando estação...")
    stations = get_station_list(token)

    if not stations:
        print("  Nenhuma estação encontrada.")
        return

    st = stations[0]
    station_id = st["id"]
    station_name = st.get("name", "Sem nome")
    print(f"  Estação: {station_name} (ID: {station_id})")

    check_generation(station_id, token, state_file)


if __name__ == "__main__":
    main()
