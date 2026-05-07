# run-monitor.ps1 - Script de execucao para o Task Scheduler
# Executa o monitor.py com todas as variaveis de ambiente configuradas

$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "5432"
$env:DB_NAME = "solarman"
$env:DB_USER = "postgres"
$env:DB_PASSWORD = "postgres123"

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

& python monitor.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "Erro na execucao do monitor.py (exit code: $LASTEXITCODE)"
    exit $LASTEXITCODE
}