# SOLARMAN Solar Monitor - Contexto do Projeto

## Motivação
Monitoramento proativo de geração de energia solar residencial.
Sistema com 2 microinversores Deye e 7 painéis fotovoltaicos.
Problema: em abril, um fio queimou e só descobrimos um mês depois.
Objetivo: alerta automático em 24h de falha + histórico diário em banco.

## Sistema Atual (testado com sucesso em 2026-05-07)

### Usina
- **Nome:** RAFAELDRUMMONDINFINIT
- **stationId:** 61949409
- **Capacidade:** 3.78 kWp
- **Localização:** Lagoa Santa, MG
- **Conexão:** DISTRIBUTED_FULLY (distribuído)
- **Tipo:** HOUSE_ROOF (residencial)

### Dispositivos
- **2 Microinversores Deye MI:**
  - `2209202725` (deviceId: 232707845)
  - `2209201606` (deviceId: 232998418)
- **2 Coletores (data loggers):**
  - `4155349359` (deviceId: 232574162)
  - `4154800881` (deviceId: 232998257)

### APIs Testadas e Funcionando
| API | Endpoint | Status |
|-----|----------|--------|
| 2.1 Token | POST /account/v1.0/token | ✅ OK |
| 4.4 Lista estações | POST /station/v1.0/list | ✅ OK |
| 4.5 Tempo real | POST /station/v1.0/realTime | ✅ OK |
| 4.2 Dispositivos | POST /station/v1.0/device | ✅ OK |
| 3.3 CurrentData (inversor) | POST /device/v1.0/currentData | ✅ OK |
| 4.3 Histórico estação | POST /station/v1.0/historical | ❌ 404 não existe |
| 3.4 Histórico inversor | POST /device/v1.0/historical | ⚠️ retorna erro RPC |

## Campos Coletados por Microinversor (Deye MI)

```
DV1-DV4:    Tensão DC por string (V)
DC1-DC4:    Corrente DC por string (A)
DP1-DP4:    Potência DC por string (W)
AV1:        Tensão AC saída (V)
AC1:        Corrente AC saída (A)
APo_t1:     Potência AC total saída (W)
AF1:        Frequência AC (Hz)
Etdy_ge0:   Produção diária (kWh)
Et_ge0:     Produção total acumulada (kWh)
Et_ge1-4:   Produção por tracker MPPT (kWh)
ST_PG1:     Status da rede (Grid connected)
AC_RDT_T1:  Temperatura do inversor (°C)
P_r1:       Potência nominal (W)
SYSTIM1:    Tempo do sistema
```

## Stack Técnica

- **Python 3** + `requests` + `psycopg2-binary`
- **PostgreSQL** para histórico (GCP Cloud SQL)
- **ntfy.sh** para notificações push no celular (gratuito)
- **Cloud Run + Cloud Scheduler** no GCP (servidorless, ~US$0-2/mês)
- **Docker** para empacotamento

## Variáveis de Ambiente

| Variável | Descrição |
|----------|-----------|
| SOLARMAN_APIID | appId fornecido pela SOLARMAN |
| SOLARMAN_APKKEY | appSecret fornecido pela SOLARMAN |
| SOLARMAN_EMAIL | email de login no app SOLARMAN |
| SOLARMAN_PASSWORD | senha de login (SHA256 internamente) |
| DB_HOST | Host do PostgreSQL |
| DB_PORT | Porta do PostgreSQL (5432) |
| DB_NAME | Nome do banco (solarman) |
| DB_USER | Usuário do banco |
| DB_PASSWORD | Senha do banco |
| NTFY_TOPIC | Tópico ntfy.sh para notificações |

## Repositório

https://github.com/RafaDru/solarman-solar-monitor