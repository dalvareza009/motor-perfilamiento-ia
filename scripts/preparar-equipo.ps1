# Instala el entorno en este computador (Python, Chrome, dependencias).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "=== Motor de perfilamiento IA — preparar equipo ==="

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
    Write-Host "Se creo .env a partir de .env.example. Completa DATABASE_URL o DB_PASSWORD."
}

if (-not (Test-Path "data\perfiles_autorizados.json")) {
    if (Test-Path "data\perfiles_autorizados.ejemplo.json") {
        Copy-Item "data\perfiles_autorizados.ejemplo.json" "data\perfiles_autorizados.json"
        Write-Host "Se creo data\perfiles_autorizados.json desde el ejemplo."
    }
}

$cfg = @{}
Get-Content .env | ForEach-Object {
    if ($_ -match "^\s*#" -or $_ -notmatch "=") { return }
    $k, $v = $_.Split("=", 2)
    $cfg[$k.Trim()] = $v.Trim()
}
$usaNeon = [string]::IsNullOrWhiteSpace($cfg["DATABASE_URL"]) -eq $false

if ($usaNeon) {
    Write-Host "Base: DATABASE_URL (Neon u otro Postgres remoto). No se instala Postgres local."
} else {
    $psql = @(
        "C:\Program Files\PostgreSQL\18\bin\psql.exe",
        "C:\Program Files\PostgreSQL\17\bin\psql.exe",
        "C:\Program Files\PostgreSQL\16\bin\psql.exe",
        "C:\Program Files\PostgreSQL\15\bin\psql.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $psql) {
        Write-Host "Falta PostgreSQL. https://www.postgresql.org/download/windows/"
        Write-Host "O usa DATABASE_URL de Neon en .env y vuelve a ejecutar este script."
        exit 1
    }
    Write-Host "Postgres OK: $psql"
    if (-not $cfg["DB_PASSWORD"]) {
        Write-Host "Pon DB_PASSWORD en .env y vuelve a ejecutar."
        exit 1
    }
    Write-Host "Restaurando base local ..."
    & "$PSScriptRoot\restaurar-base.ps1"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Host "AVISO: no esta Ollama. Si usas LLM_API_KEY de Vercel no hace falta."
    Write-Host "Para modelo 100% local: https://ollama.com/download"
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
Write-Host "Clave: la de DEMO_CLAVE en .env (por defecto jefe-prueba-2026). Rol: Administrador."
