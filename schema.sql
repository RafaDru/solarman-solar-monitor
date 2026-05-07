-- ============================================================
-- SOLARMAN Solar Monitor - PostgreSQL Schema
-- ============================================================

-- Extensão para timestamps
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- Tabela: usinas (estações SOLARMAN)
-- ============================================================
CREATE TABLE stations (
    id BIGINT PRIMARY KEY,                    -- stationId da API
    name VARCHAR(255),
    address TEXT,
    installed_capacity_kwp DECIMAL(8,3),
    station_type VARCHAR(50),                 -- HOUSE_ROOF, etc
    grid_type VARCHAR(50),                    -- DISTRIBUTED_FULLY, etc
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    timezone VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Tabela: dispositivos (microinversores, coletores)
-- ============================================================
CREATE TABLE devices (
    id BIGINT PRIMARY KEY,                    -- deviceId da API
    device_sn VARCHAR(50) UNIQUE NOT NULL,
    device_type VARCHAR(50),                  -- MICRO_INVERTER, COLLECTOR, INVERTER
    station_id BIGINT REFERENCES stations(id),
    rated_power_w DECIMAL(10,2),              -- Potência nominal (2000W para Deye MI)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Tabela: leituras em tempo real (snapshot horário)
-- ============================================================
CREATE TABLE readings_realtime (
    id BIGSERIAL PRIMARY KEY,
    station_id BIGINT REFERENCES stations(id),
    recorded_at TIMESTAMPTZ DEFAULT NOW(),

    -- Dados da estação (API 4.5)
    generation_power_w DECIMAL(10,2),         -- Geração atual em W
    use_power_w DECIMAL(10,2),                 -- Consumo atual em W
    grid_power_w DECIMAL(10,2),                -- Energia da rede em W
    purchase_power_w DECIMAL(10,2),            -- Energia comprada (W)
    wire_power_w DECIMAL(10,2),                -- Energia injetada na rede (W)
    battery_power_w DECIMAL(10,2),            -- Potência bateria (W)
    battery_soc_pct DECIMAL(5,2),             -- Estado de carga bateria (%)
    charge_power_w DECIMAL(10,2),             -- Potência de carga (W)
    discharge_power_w DECIMAL(10,2),          -- Potência de descarga (W)
    irradiate_intensity DECIMAL(8,2),         -- Irradiação solar (W/m²)
    generation_total_kwh DECIMAL(12,3),       -- Total gerado histórico (kWh)
    last_update_time TIMESTAMPTZ,             -- Timestamp do dispositivo

    -- Dados agregados dos microinversores (soma)
    total_dc_power_w DECIMAL(10,2),          -- Soma DC power de todos inversores
    total_ac_output_w DECIMAL(10,2),          -- Soma AC output de todos inversores
    avg_grid_frequency DECIMAL(6,2),          -- Frequência média da rede (Hz)
    max_inverter_temp DECIMAL(6,2),           -- Temperatura máxima dos inversores (°C)

    UNIQUE(station_id, recorded_at)
);

-- ============================================================
-- Tabela: dados por microinversor (leitura atual)
-- ============================================================
CREATE TABLE device_readings (
    id BIGSERIAL PRIMARY KEY,
    device_id BIGINT REFERENCES devices(id),
    recorded_at TIMESTAMPTZ DEFAULT NOW(),

    -- DC (painéis)
    dc_voltage_pv1 DECIMAL(6,2),              -- V
    dc_voltage_pv2 DECIMAL(6,2),
    dc_voltage_pv3 DECIMAL(6,2),
    dc_voltage_pv4 DECIMAL(6,2),
    dc_current_pv1 DECIMAL(6,2),              -- A
    dc_current_pv2 DECIMAL(6,2),
    dc_current_pv3 DECIMAL(6,2),
    dc_current_pv4 DECIMAL(6,2),
    dc_power_pv1 DECIMAL(8,2),                -- W
    dc_power_pv2 DECIMAL(8,2),
    dc_power_pv3 DECIMAL(8,2),
    dc_power_pv4 DECIMAL(8,2),

    -- AC (saída)
    ac_voltage_1 DECIMAL(7,2),               -- V
    ac_current_1 DECIMAL(6,2),               -- A
    ac_output_power_w DECIMAL(8,2),          -- W (APo_t1)
    ac_frequency DECIMAL(5,2),               -- Hz

    -- Energia
    total_production_kwh DECIMAL(12,3),      -- Total acumulado (kWh)
    daily_production_kwh DECIMAL(8,3),       -- Produção do dia (kWh)

    -- Status
    grid_status VARCHAR(50),                -- Grid connected, etc
    inverter_temp DECIMAL(6,2),              -- °C

    UNIQUE(device_id, recorded_at)
);

-- ============================================================
-- Tabela: produção diária por usina (agregado diário)
-- ============================================================
CREATE TABLE daily_production (
    id BIGSERIAL PRIMARY KEY,
    station_id BIGINT REFERENCES stations(id),
    date DATE NOT NULL,

    -- Totais do dia
    total_generation_kwh DECIMAL(12,3),      -- Total gerado no dia (kWh)
    total_consumption_kwh DECIMAL(12,3),     -- Total consumido no dia
    total_purchase_kwh DECIMAL(12,3),        -- Total comprado da rede
    total_export_kwh DECIMAL(12,3),         -- Total exportado para rede

    -- Pico
    peak_power_w DECIMAL(10,2),              -- Maior potênciainstantânea (W)

    -- Dados de produção por inversor (soma dos daily_production)
    -- Total Production: soma de Et_ge0 dos inversores no fim do dia
    -- ou pode ser calculado de readings_realtime
    -- Por enquanto é NULL e pode ser preenchido via lógica

    UNIQUE(station_id, date)
);

-- ============================================================
-- Tabela: alertas
-- ============================================================
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    station_id BIGINT REFERENCES stations(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    alert_type VARCHAR(50),                  -- NO_GENERATION_24H, DEVICE_OFFLINE, etc
    severity VARCHAR(20),                    -- INFO, WARNING, CRITICAL
    message TEXT,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMPTZ
);

-- ============================================================
-- Índices para performance
-- ============================================================
CREATE INDEX idx_readings_realtime_station_time ON readings_realtime(station_id, recorded_at DESC);
CREATE INDEX idx_device_readings_device_time ON device_readings(device_id, recorded_at DESC);
CREATE INDEX idx_daily_production_station_date ON daily_production(station_id, date DESC);
CREATE INDEX idx_alerts_station ON alerts(station_id, created_at DESC);
CREATE INDEX idx_alerts_unack ON alerts(acknowledged, created_at DESC) WHERE acknowledged = FALSE;

-- ============================================================
-- View: resumo diário (para dashboards)
-- ============================================================
CREATE VIEW v_daily_summary AS
SELECT
    d.station_id,
    d.date,
    d.total_generation_kwh,
    d.total_purchase_kwh,
    d.total_export_kwh,
    ROUND(d.total_generation_kwh * 0.88, 3) AS savings_brl,  -- tarifa aprox R$0.88/kWh
    s.name AS station_name
FROM daily_production d
JOIN stations s ON s.id = d.station_id;