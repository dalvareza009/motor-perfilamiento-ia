# Instala el entorno 100% local (Python, Chrome, Postgres, Ollama).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "=== Motor de perfilamiento IA — preparar equipo (local) ==="

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "Falta Python 3.12+. https://www.python.org/downloads/  (marca Add to PATH)"
    exit 1
}
python --version

$chrome = @(
    "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) {
    Write-Host "Falta Google Chrome. https://www.google.com/chrome/  (no uses Edge)"
    exit 1
}
Write-Host "Chrome OK"

if (-not (Test-Path .venv)) {
    Write-Host "Creando entorno .venv ..."
    python -m venv .venv
}
Write-Host "Instalando dependencias Python ..."
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Se creo .env. Editalo y pon DB_PASSWORD igual a la de Postgres."
}

$psql = @(
    "C:\Program Files\PostgreSQL\18\bin\psql.exe",
    "C:\Program Files\PostgreSQL\17\bin\psql.exe",
    "C:\Program Files\PostgreSQL\16\bin\psql.exe",
    "C:\Program Files\PostgreSQL\15\bin\psql.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $psql) {
    Write-Host "Falta PostgreSQL. https://www.postgresql.org/download/windows/"
    exit 1
}
Write-Host "Postgres OK: $psql"

Write-Host "Restaurando base local ..."
& "$PSScriptRoot\restaurar-base.ps1"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Host "AVISO: no esta Ollama. Sin el modelo no hay recomendaciones ni borradores."
    Write-Host "Instala https://ollama.com/download y luego:"
    Write-Host "  ollama pull qwen3:4b-instruct"
    Write-Host "  ollama pull nomic-embed-text"
} else {
    Write-Host "Descargando modelos de Ollama (puede tardar) ..."
    ollama pull qwen3:4b-instruct
    ollama pull nomic-embed-text
}

Write-Host ""
Write-Host "Listo. Arranca con scripts\iniciar.ps1"
Write-Host "Luego abre http://127.0.0.1:8000"
