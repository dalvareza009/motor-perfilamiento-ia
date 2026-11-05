# Arranca el motor en este computador.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv\Scripts\python.exe)) {
    Write-Host "Primero ejecuta INSTALAR.bat o scripts\preparar-equipo.ps1"
    exit 1
}
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Se creo .env. Completa DATABASE_URL o DB_PASSWORD y vuelve a ejecutar iniciar.ps1"
    exit 1
}

$clave = "jefe-prueba-2026"
Get-Content .env | ForEach-Object {
    if ($_ -match "^\s*DEMO_CLAVE\s*=\s*(.+)$") { $script:clave = $Matches[1].Trim() }
}

Write-Host "Abre en Chrome: http://127.0.0.1:8000"
Write-Host "Clave de acceso: $clave"
Write-Host "Rol: Administrador."
.\.venv\Scripts\python.exe -m app.api
