# Arranca el motor en este computador (todo local).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv\Scripts\python.exe)) {
    Write-Host "Primero ejecuta scripts\preparar-equipo.ps1"
    exit 1
}
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Se creo .env. Pon DB_PASSWORD y vuelve a ejecutar iniciar.ps1"
    exit 1
}

Write-Host "Abre en Chrome: http://127.0.0.1:8000"
Write-Host "Clave de acceso: dejala vacia. Rol: Administrador."
.\.venv\Scripts\python.exe -m app.api
