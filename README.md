# SOLARMAN Solar Monitor

Monitoramento proativo de geração de energia solar via API SOLARMAN (v1.1.6).

## Como obter as chaves de API

Envie email para `service@solarmanpv.com` solicitando acesso à OpenAPI.
Informe que é um usuário residencial com microinversores Deye e 7 painéis.

## Configuração

### 1. Defina as variáveis de ambiente

**PowerShell (Windows):**
```powershell
$env:SOLARMAN_APIKEY = "seu_app_id"
$env:SOLARMAN_APKKEY = "seu_app_secret"
$env:SOLARMAN_EMAIL = "seu_email_cadastrado"
$env:SOLARMAN_PASSWORD = "sua_senha"
$env:SOLARMAN_WEBHOOK = "https://hooks.exemplo.com/alertas"  # opcional
```

**Linux/macOS:**
```bash
export SOLARMAN_APIKEY="seu_app_id"
export SOLARMAN_APKKEY="seu_app_secret"
export SOLARMAN_EMAIL="seu_email"
export SOLARMAN_PASSWORD="sua_senha"
```

Ou copie `.env.sample` para `.env` (não versionado) e use `python-dotenv`.

### 2. Instale as dependências

```bash
pip install -r requirements.txt
```

### 3. Execute

```bash
python monitor.py
```

## Agendamento

**Windows (Task Scheduler):** crie uma tarefa diária executando `python monitor.py`.

**Linux (cron):**
```cron
0 8 * * * cd /caminho/solarman-solar-monitor && python monitor.py
```

## Alerta de falha

O script mantém um arquivo `state.json` com o timestamp da última geração.
Se a geração ficar 24h sem produzir energia, um alerta é disparado via webhook.

## Estrutura da API

Base URL: `https://globalapi.solarmanpv.com`

| Etapa | Endpoint | Descrição |
|-------|----------|-----------|
| 1 | `POST /account/v1.0/token?appId=X` | Obter token (password em SHA256) |
| 2 | `POST /station/v1.0/list` | Listar estações |
| 3 | `POST /station/v1.0/realtime` | Dados em tempo real da estação |

Docs: https://doc.solarmanpv.com

## Repositório

https://github.com/RafaDru/solarman-solar-monitor
