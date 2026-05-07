# SOLARMAN Solar Monitor - Contexto do Projeto

## Motivação
Monitoramento proativo da geração de energia solar residencial.
Sistema com 2 microinversores Deye e 7 painéis fotovoltaicos.
Antes: consulta manual via app SOLARMAN. Em abril, um fio queimou e só
descobrimos um mês depois. Objetivo: alerta automático em até 24h de falha.

## Stack
- Python 3 + requests
- API SOLARMAN OpenAPI v1.1.6 (globalapi.solarmanpv.com)
- Armazenamento local via state.json
- Webhook para alertas (Telegram/Discord/ntfy)

## APIs utilizadas (documentação oficial)
doc.solarmanpv.com

- **2.1** POST `/account/v1.0/token` - Autenticação (password SHA256)
- **4.4** POST `/station/v1.0/list` - Lista de estações (usina)
- **4.5** POST `/station/v1.0/realTime` - Dados em tempo real

## Fluxo
1. Ler credenciais de variáveis de ambiente
2. Obter token de acesso (válido por 2 meses)
3. Buscar lista de estações -> obter stationId
4. Consultar realTime -> ler generationPower
5. Se geração = 0 por 24h+ -> disparar alerta via webhook

## Variáveis de Ambiente
| Variável | Descrição |
|----------|-----------|
| SOLARMAN_APIKEY | appId fornecido pela SOLARMAN |
| SOLARMAN_APKKEY | appSecret fornecido pela SOLARMAN |
| SOLARMAN_EMAIL | email de login no app SOLARMAN |
| SOLARMAN_PASSWORD | senha de login no app SOLARMAN |
| SOLARMAN_WEBHOOK | URL para alertas (opcional) |

## Deploy Planejado
GCP (Google Cloud Platform) - servidor pequeno (e2-micro ou Cloud Run)

## Estrutura do Repositório
```
solarman-solar-monitor/
  monitor.py        # Script principal
  state.json        # Estado local (não versionado)
  config.json       # Config local (não versionado)
  .env              # Env local (não versionado)
  .env.sample       # Template de env
  config.json.sample# Template de config
  requirements.txt  # Dependências
  CONTEXT.md        # Este documento
  README.md         # Instruções
```

## Comando para testar
```powershell
cd C:\Users\rafae\solarman-solar-monitor
pip install requests -q
python monitor.py
```
