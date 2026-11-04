# Crea la base local y carga el dump (schema + datos).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .env)) {
    Write-Host "Falta .env. Copia .env.example a .env y pon DB_PASSWORD."
    exit 1
}

$cfg = @{}
Get-Content .env | ForEach-Object {
    if ($_ -match "^\s*#" -or $_ -notmatch "=") { return }
    $k, $v = $_.Split("=", 2)
    $cfg[$k.Trim()] = $v.Trim()
}
$hostName = if ($cfg.DB_HOST) { $cfg.DB_HOST } else { "localhost" }
$port = if ($cfg.DB_PORT) { $cfg.DB_PORT } else { "5432" }
$db = if ($cfg.DB_NAME) { $cfg.DB_NAME } else { "base_datos" }
$user = if ($cfg.DB_USER) { $cfg.DB_USER } else { "postgres" }
$env:PGPASSWORD = $cfg.DB_PASSWORD
$env:PGCLIENTENCODING = "UTF8"

$psql = @(
    "C:\Program Files\PostgreSQL\18\bin\psql.exe",
    "C:\Program Files\PostgreSQL\17\bin\psql.exe",
    "C:\Program Files\PostgreSQL\16\bin\psql.exe",
    "C:\Program Files\PostgreSQL\15\bin\psql.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $psql) {
    Write-Host "No se encontro psql.exe"
    exit 1
}

$dump = Join-Path "datos_iniciales" "base_datos.sql"
if (-not (Test-Path $dump)) {
    Write-Host "Falta $dump"
    exit 1
}

Write-Host "Creando base $db si no existe ..."
& $psql -h $hostName -p $port -U $user -d postgres -v ON_ERROR_STOP=0 -c "CREATE DATABASE $db;" 2>$null | Out-Null

Write-Host "Cargando $dump ..."
& $psql -h $hostName -p $port -U $user -d $db -v ON_ERROR_STOP=1 -f $dump
if ($LASTEXITCODE -ne 0) {
    Write-Host "Fallo al restaurar. Revisa DB_PASSWORD en .env y que el servicio PostgreSQL este en ejecucion."
    exit $LASTEXITCODE
}
Write-Host "Base local lista."
