#!/usr/bin/env python3
"""SOLARMAN Solar Monitor - Coleta diária de dados + alertas

Coleta dados da API SOLARMAN e armazena no PostgreSQL.
Executado diariamente via Cloud Scheduler (GCP) ou cron.
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import requests

BASE_URL = "https://globalapi.solarmanpv.com"

ENV_MAP = {
    "appId": "SOLARMAN_APIID",
    "appSecret": "SOLARMAN_APKKEY",
    "email": "SOLARMAN_EMAIL",
    "password": "SOLARMAN_PASSWORD",
}
ENV_DB = {
    "host": "DB_HOST",
    "port": "DB_PORT",
    "database": "DB_NAME",
    "user": "DB_USER",
    "password": "DB_PASSWORD",
}


def sha256_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()


def load_config(required_keys):
    config = {}
    for key, env_var in required_keys.items():
        value = os.getenv(env_var)
        if not value:
            print(f"Erro: variavel de ambiente {env_var} nao definida.")
            sys.exit(1)
        config[key] = value
    return config


def api_post(path, token, body=None):
    resp = requests.post(
        f"{BASE_URL}{path}",
        headers={"Content-Type": "application/json", "Authorization": f"bearer {token}"},
        json=body or {}
    )
    resp.raise_for_status()
    return resp.json()


def get_token(config):
    resp = requests.post(
        f"{BASE_URL}/account/v1.0/token?appId={config['appId']}&language=en",
        headers={"Content-Type": "application/json"},
        json={
            "appSecret": config["appSecret"],
            "email": config["email"],
            "password": sha256_hash(config["password"]),
        }
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def to_decimal(value):
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def flatten_device_data(data_list):
    result = {}
    for item in data_list:
        key = item.get("key", "")
        val = item.get("value", "")
        unit = item.get("unit", "") or ""
        name = item.get("name", "")
        result[key] = {"value": val, "unit": unit, "name": name}
    return result


def extract_field(flat, keys, default=None):
    for k in keys:
        if k in flat:
            v = flat[k]["value"]
            if v and v != "null" and v != "None":
                try:
                    return Decimal(str(v))
                except (InvalidOperation, ValueError):
                    return v
    return default


def send_daily_summary(conn, station_name):
    cur = conn.cursor()
    try:
        import psycopg2.extras
    except ImportError:
        return

    topic = os.getenv("NTFY_TOPIC")
    if not topic:
        return

    cur.execute("""
        SELECT SUM(daily_production_kwh)
        FROM device_readings dr
        JOIN devices d ON d.id = dr.device_id
        WHERE recorded_at::date = CURRENT_DATE
          AND d.device_type IN ('MICRO_INVERTER', 'INVERTER')
    """)
    today_kwh = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT SUM(daily_production_kwh)
        FROM device_readings dr
        JOIN devices d ON d.id = dr.device_id
        WHERE DATE_TRUNC('month', recorded_at) = DATE_TRUNC('month', CURRENT_DATE)
          AND d.device_type IN ('MICRO_INVERTER', 'INVERTER')
    """)
    month_kwh = cur.fetchone()[0] or 0

    avg_daily = float(os.getenv("AVG_DAILY_KWH", "18.0"))
    today_val = float(today_kwh)

    if today_val < avg_daily * 0.7:
        status = "MUITO ABAIXO"
    elif today_val < avg_daily:
        status = "ABAIXO DA MEDIA"
    elif today_val > avg_daily * 1.2:
        status = "MUITO ACIMA"
    elif today_val > avg_daily:
        status = "ACIMA DA MEDIA"
    else:
        status = "NA MEDIA"

    emoji = {"MUITO ABAIXO": "🔴", "ABAIXO DA MEDIA": "🟡",
             "NA MEDIA": "🟢", "ACIMA DA MEDIA": "🟢",
             "MUITO ACIMA": "🔵"}.get(status, "⚪")

    msg = (
        f"{emoji} SOLARMAN - Resumo Diario\n\n"
        f"Hoje: {today_val:.2f} kWh ({status})\n"
        f"Mes: {float(month_kwh):.2f} kWh\n"
        f"Referencia diaria: {avg_daily:.1f} kWh"
    )

    try:
        resp = requests.post(
            f"https://ntfy.sh/{topic}",
            data=msg.encode("utf-8"),
            headers={"Title": "SOLARMAN - Resumo", "Priority": "default"},
            timeout=10
        )
        print(f"  Resumo diario enviado: {resp.status_code}")
    except Exception as e:
        print(f"  Erro ao enviar resumo: {e}")


def send_alert(alert_title, message):
    ntfy_url = os.getenv("NTFY_TOPIC")
    if not ntfy_url:
        return
    try:
        resp = requests.post(
            f"https://ntfy.sh/{ntfy_url}",
            data=f"{alert_title}\n\n{message}".encode("utf-8"),
            headers={"Title": alert_title, "Priority": "high"},
            timeout=10
        )
        print(f"  Alerta enviado: {resp.status_code}")
    except Exception as e:
        print(f"  Erro ao enviar alerta: {e}")


def check_generation_failure(now, state_file, station_id):
    state = {}
    if os.path.exists(state_file):
        with open(state_file) as f:
            state = json.load(f)

    last_gen = state.get("last_generation_time")
    alert_sent = state.get("alert_sent_24h", False)

    if last_gen:
        last_time = datetime.fromisoformat(last_gen)
        hours = (now - last_time).total_seconds() / 3600
        print(f"  Horas desde ultima geracao: {hours:.1f}h")
        if hours >= 24 and not alert_sent:
            msg = f"ALERTA: Sem geracao solar ha {hours:.1f}h na usina {station_id}!"
            send_alert("☀️ SOLAR - Sem Geracao", msg)
            state["alert_sent_24h"] = True
            state["last_alert_at"] = now.isoformat()

    state["last_check"] = now.isoformat()
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)


def upsert_station(cur, station):
    cur.execute("""
        INSERT INTO stations (id, name, address, installed_capacity_kwp,
                               station_type, grid_type, latitude, longitude, timezone)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            address = EXCLUDED.address,
            installed_capacity_kwp = EXCLUDED.installed_capacity_kwp,
            station_type = EXCLUDED.station_type,
            grid_type = EXCLUDED.grid_type,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            timezone = EXCLUDED.timezone,
            updated_at = NOW()
    """, (
        station["id"],
        station.get("name"),
        station.get("locationAddress"),
        to_decimal(station.get("installedCapacity")),
        station.get("type"),
        station.get("gridInterconnectionType"),
        to_decimal(station.get("locationLat")),
        to_decimal(station.get("locationLng")),
        station.get("regionTimezone"),
    ))


def upsert_device(cur, device, station_id):
    cur.execute("""
        INSERT INTO devices (id, device_sn, device_type, station_id)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            device_sn = EXCLUDED.device_sn,
            device_type = EXCLUDED.device_type,
            station_id = EXCLUDED.station_id,
            updated_at = NOW()
    """, (
        device["deviceId"],
        device["deviceSn"],
        device["deviceType"],
        station_id,
    ))


def insert_realtime(cur, station_id, data, total_dc_w, total_ac_w, max_temp):
    cur.execute("""
        INSERT INTO readings_realtime (
            station_id, recorded_at, generation_power_w,
            use_power_w, grid_power_w, purchase_power_w,
            wire_power_w, battery_power_w, battery_soc_pct,
            charge_power_w, discharge_power_w, irradiate_intensity,
            generation_total_kwh, last_update_time,
            total_dc_power_w, total_ac_output_w, max_inverter_temp
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (station_id, recorded_at) DO UPDATE SET
            generation_power_w = EXCLUDED.generation_power_w,
            use_power_w = EXCLUDED.use_power_w,
            grid_power_w = EXCLUDED.grid_power_w,
            purchase_power_w = EXCLUDED.purchase_power_w,
            wire_power_w = EXCLUDED.wire_power_w,
            battery_power_w = EXCLUDED.battery_power_w,
            battery_soc_pct = EXCLUDED.battery_soc_pct,
            charge_power_w = EXCLUDED.charge_power_w,
            discharge_power_w = EXCLUDED.discharge_power_w,
            irradiate_intensity = EXCLUDED.irradiate_intensity,
            generation_total_kwh = EXCLUDED.generation_total_kwh,
            last_update_time = EXCLUDED.last_update_time,
            total_dc_power_w = EXCLUDED.total_dc_power_w,
            total_ac_output_w = EXCLUDED.total_ac_output_w,
            max_inverter_temp = EXCLUDED.max_inverter_temp
    """, (
        station_id,
        datetime.now(timezone.utc),
        to_decimal(data.get("generationPower")),
        to_decimal(data.get("usePower")),
        to_decimal(data.get("gridPower")),
        to_decimal(data.get("purchasePower")),
        to_decimal(data.get("wirePower")),
        to_decimal(data.get("batteryPower")),
        to_decimal(data.get("batterySoc")),
        to_decimal(data.get("chargePower")),
        to_decimal(data.get("dischargePower")),
        to_decimal(data.get("irradiateIntensity")),
        to_decimal(data.get("generationTotal")),
        datetime.fromtimestamp(float(data["lastUpdateTime"]), tz=timezone.utc)
            if data.get("lastUpdateTime") else None,
        to_decimal(total_dc_w),
        to_decimal(total_ac_w),
        to_decimal(max_temp),
    ))


def insert_device_reading(cur, device_id, flat, now):
    cur.execute("""
        INSERT INTO device_readings (
            device_id, recorded_at,
            dc_voltage_pv1, dc_voltage_pv2, dc_voltage_pv3, dc_voltage_pv4,
            dc_current_pv1, dc_current_pv2, dc_current_pv3, dc_current_pv4,
            dc_power_pv1, dc_power_pv2, dc_power_pv3, dc_power_pv4,
            ac_voltage_1, ac_current_1, ac_output_power_w, ac_frequency,
            total_production_kwh, daily_production_kwh,
            grid_status, inverter_temp
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (device_id, recorded_at) DO UPDATE SET
            dc_voltage_pv1 = EXCLUDED.dc_voltage_pv1,
            dc_voltage_pv2 = EXCLUDED.dc_voltage_pv2,
            dc_voltage_pv3 = EXCLUDED.dc_voltage_pv3,
            dc_voltage_pv4 = EXCLUDED.dc_voltage_pv4,
            dc_current_pv1 = EXCLUDED.dc_current_pv1,
            dc_current_pv2 = EXCLUDED.dc_current_pv2,
            dc_current_pv3 = EXCLUDED.dc_current_pv3,
            dc_current_pv4 = EXCLUDED.dc_current_pv4,
            dc_power_pv1 = EXCLUDED.dc_power_pv1,
            dc_power_pv2 = EXCLUDED.dc_power_pv2,
            dc_power_pv3 = EXCLUDED.dc_power_pv3,
            dc_power_pv4 = EXCLUDED.dc_power_pv4,
            ac_voltage_1 = EXCLUDED.ac_voltage_1,
            ac_current_1 = EXCLUDED.ac_current_1,
            ac_output_power_w = EXCLUDED.ac_output_power_w,
            ac_frequency = EXCLUDED.ac_frequency,
            total_production_kwh = EXCLUDED.total_production_kwh,
            daily_production_kwh = EXCLUDED.daily_production_kwh,
            grid_status = EXCLUDED.grid_status,
            inverter_temp = EXCLUDED.inverter_temp
    """, (
        device_id,
        now,
        extract_field(flat, ["DV1"]),
        extract_field(flat, ["DV2"]),
        extract_field(flat, ["DV3"]),
        extract_field(flat, ["DV4"]),
        extract_field(flat, ["DC1"]),
        extract_field(flat, ["DC2"]),
        extract_field(flat, ["DC3"]),
        extract_field(flat, ["DC4"]),
        extract_field(flat, ["DP1"]),
        extract_field(flat, ["DP2"]),
        extract_field(flat, ["DP3"]),
        extract_field(flat, ["DP4"]),
        extract_field(flat, ["AV1"]),
        extract_field(flat, ["AC1"]),
        extract_field(flat, ["APo_t1"]),
        extract_field(flat, ["AF1"]),
        extract_field(flat, ["Et_ge0"]),
        extract_field(flat, ["Etdy_ge0"]),
        extract_field(flat, ["ST_PG1"]),
        extract_field(flat, ["AC_RDT_T1"]),
    ))


def insert_alert(cur, station_id, alert_type, severity, message):
    cur.execute("""
        INSERT INTO alerts (station_id, alert_type, severity, message)
        VALUES (%s, %s, %s, %s)
    """, (station_id, alert_type, severity, message))


def check_device_offline(devices, station_id, cur):
    for dev in devices:
        if dev.get("deviceType") in ("MICRO_INVERTER", "INVERTER"):
            status = dev.get("connectStatus", 0)
            if status == 0:
                msg = f"Inversor {dev['deviceSn']} offline!"
                insert_alert(cur, station_id, "DEVICE_OFFLINE", "CRITICAL", msg)
                send_alert("⚠️ SOLAR - Inversor Offline", msg)


def run(conn, token, stations):
    station = stations[0]
    st_id = station["id"]
    now = datetime.now(timezone.utc)
    state_file = os.path.join(os.path.dirname(__file__), "state.json")

    print(f"  Estacao: {station.get('name')} (ID: {st_id})")

    upsert_station(conn.cursor(), station)

    devices_resp = api_post("/station/v1.0/device", token,
                            {"page": 1, "size": 20, "stationId": st_id})
    devices = devices_resp.get("deviceListItems", [])

    inverters = []
    total_dc_w = Decimal("0")
    total_ac_w = Decimal("0")
    max_temp = None

    for dev in devices:
        dev_id = dev["deviceId"]
        upsert_device(conn.cursor(), dev, st_id)
        check_device_offline([dev], st_id, conn.cursor())

        if dev.get("deviceType") in ("MICRO_INVERTER", "INVERTER"):
            try:
                dev_data = api_post("/device/v1.0/currentData", token,
                                    {"deviceSn": dev["deviceSn"]})
                flat = flatten_device_data(dev_data.get("dataList", []))

                insert_device_reading(conn.cursor(), dev_id, flat, now)

                dc_power = sum([
                    extract_field(flat, ["DP1"]) or Decimal("0"),
                    extract_field(flat, ["DP2"]) or Decimal("0"),
                    extract_field(flat, ["DP3"]) or Decimal("0"),
                    extract_field(flat, ["DP4"]) or Decimal("0"),
                ])
                ac_power = extract_field(flat, ["APo_t1"]) or Decimal("0")
                temp = extract_field(flat, ["AC_RDT_T1"])

                total_dc_w += dc_power
                total_ac_w += ac_power

                if temp is not None:
                    if max_temp is None or temp > max_temp:
                        max_temp = temp

                inverters.append({
                    "sn": dev["deviceSn"],
                    "ac_power": ac_power,
                    "dc_power": dc_power,
                    "daily_kwh": extract_field(flat, ["Etdy_ge0"]),
                    "total_kwh": extract_field(flat, ["Et_ge0"]),
                    "temp": temp,
                })
                print(f"    Microinversor {dev['deviceSn']}: "
                      f"AC={ac_power}W DC={dc_power}W "
                      f"Hoje={extract_field(flat, ['Etdy_ge0'])}kWh "
                      f"Temp={temp}°C" if temp else "")
            except Exception as e:
                print(f"    Erro ao coletar dados do inversor {dev['deviceSn']}: {e}")

    realtime = api_post("/station/v1.0/realTime", token, {"stationId": st_id})
    print(f"  Geracao atual: {realtime.get('generationPower')}W | "
          f"Total historico: {realtime.get('generationTotal')}kWh")

    insert_realtime(conn.cursor(), st_id, realtime, total_dc_w, total_ac_w, max_temp)

    conn.commit()

    check_generation_failure(datetime.now(), state_file, st_id)

    print(f"  {len(inverters)} microinversores monitorados")
    print(f"  Total DC: {total_dc_w}W | Total AC: {total_ac_w}W")


def main():
    print(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] SOLARMAN Monitor - Coleta diaria")
    print(f"  Autenticando...")

    api_config = load_config(ENV_MAP)
    token = get_token(api_config)
    print(f"  Token OK")

    db_config = load_config(ENV_DB)
    print(f"  Conectando ao PostgreSQL...")

    try:
        import psycopg2
    except ImportError:
        print("  ERRO: psycopg2 nao instalado. Execute: pip install psycopg2-binary")
        sys.exit(1)

    conn = psycopg2.connect(
        host=db_config["host"],
        port=db_config["port"],
        database=db_config["database"],
        user=db_config["user"],
        password=db_config["password"],
    )
    print(f"  DB OK")
    conn.autocommit = False

    print(f"  Buscando estacoes...")
    stations = api_post("/station/v1.0/list", token, {"page": 1, "size": 10})
    station_list = stations.get("stationList", [])

    if not station_list:
        print("  Nenhuma estacao encontrada.")
        conn.close()
        return

    run(conn, token, station_list)
    send_daily_summary(conn, station_list[0].get("name", "Usina"))
    conn.close()
    print(f"\n  Coleta finalizada com sucesso!\n")


if __name__ == "__main__":
    main()