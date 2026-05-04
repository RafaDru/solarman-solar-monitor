# SOLARMAN Solar Monitor

Monitoramento proativo de geração de energia solar via API SOLARMAN.

## Configuração

1. Solicite acesso à API enviando email para `service@solarmanpv.com` com:
   - Seu nome e CPF
   - Que você é um usuário residencial com microinversores Deye
   - Que deseja monitorar a geração via API para alertas proativos

2. Após receber `appId` e `appSecret`, copie o arquivo de configuração:
   ```bash
   cp config.json.sample config.json
   ```

3. Edite `config.json` com suas credenciais.

4. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

## Uso

Execução manual:
```bash
python monitor.py
```

Agendamento (Windows - Task Scheduler ou cron no Linux):
```bash
# Exemplo: executar 1x por dia às 8h
python monitor.py
```

## Alertas

O script alerta quando não há geração por 24 horas. Configure webhook (ex: Slack, Discord, Telegram) no `config.json`.

## Repositório

https://github.com/RafaDru/solarman-solar-monitor
