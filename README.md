# SOLARMAN Solar Monitor

Monitoramento proativo de geração solar com coleta histórica em PostgreSQL.

## Arquitetura

```
┌─────────────┐     ┌─────────────────┐     ┌────────────┐
│  SOLARMAN   │────▶│  monitor.py     │────▶│ PostgreSQL │
│  API v1.1.6 │     │  (Cloud Run)    │     │ (GCP DB)   │
└─────────────┘     └────────┬────────┘     └──────┬─────┘
                             │                    │
                             ▼                    ▼
                    ┌─────────────────┐     ┌────────────┐
                    │  ntfy.sh        │     │   Alerta   │
                    │  (notificacao)  │     │  24h sem   │
                    └─────────────────┘     │  geracao   │
                                            └────────────┘
```

## Coleta de Dados

### API 4.4 - Estações
- ID, nome, endereço, capacidade instalada (kWp)
- Coordenadas geográficas, tipo de conexão

### API 4.5 - Tempo Real da Usina
- Geração, consumo, rede, bateria (W)
- Irradiação solar, SOC bateria

### API 3.3 - Microinversores (por dispositivo)
- DC: tensão, corrente, potência PV1-PV4 (V, A, W)
- AC: tensão, corrente, potência de saída, frequência
- Produção total (kWh) e diária (kWh)
- Temperatura do inversor, status da rede

### API 4.2 - Dispositivos
- Lista de microinversores e coletores
- Status de conexão (online/offline)

## Requisitos

- Python 3.10+
- PostgreSQL 14+

## Configuração

### Variáveis de Ambiente

```powershell
# API SOLARMAN
$env:SOLARMAN_APIID = "seu_app_id"
$env:SOLARMAN_APKKEY = "seu_app_secret"
$env:SOLARMAN_EMAIL = "seu_email"
$env:SOLARMAN_PASSWORD = "sua_senha"

# PostgreSQL (GCP Cloud SQL)
$env:DB_HOST = "ip_do_servidor"
$env:DB_PORT = "5432"
$env:DB_NAME = "solarman"
$env:DB_USER = "postgres"
$env:DB_PASSWORD = "senha"

# Notificação (opcional)
$env:NTFY_TOPIC = "nome_do_topico_ntfy"
```

### Instalar dependências

```bash
pip install -r requirements.txt
```

### Criar banco de dados

```bash
psql -h IP_DO_SERVIDOR -U postgres -d postgres -c "CREATE DATABASE solarman;"
psql -h IP_DO_SERVIDOR -U postgres -d solarman -f schema.sql
```

## Execução

```bash
python monitor.py
```

## Deploy GCP

### Cloud Run (servidorless, ~$0-2/mês)

1. Habilite Cloud Run, Cloud SQL, Secret Manager no GCP Console
2. Configure Cloud SQL (PostgreSQL) com usuário e senha
3. Crie secrets no Secret Manager para cada variável de ambiente
4. Deploy:

```bash
gcloud run deploy solarman-monitor \
  --source . \
  --region southamerica-east1 \
  --set-env-vars "DB_HOST=/cloudsql/projeto:regiao:instancia" \
  --set-secrets "SOLARMAN_APIID:latest,..." \
  --add-cloudsql-instances "projeto:regiao:instancia"
```

5. Cloud Scheduler: disparador diário às 20:00 BRT

```bash
gcloud scheduler jobs create http solarman-daily \
  --schedule="0 20 * * *" \
  --uri="https://URL_DO_CLOUD_RUN" \
  --time-zone="America/Sao_Paulo"
```

## Schema do Banco

Ver `schema.sql` para a estrutura completa com:
- `stations` - dados da usina
- `devices` - microinversores e coletores
- `readings_realtime` - snapshot horário
- `device_readings` - leitura atual por inversor
- `daily_production` - produção agregada diária
- `alerts` - alertas de falha

## Repositório

https://github.com/RafaDru/solarman-solar-monitor