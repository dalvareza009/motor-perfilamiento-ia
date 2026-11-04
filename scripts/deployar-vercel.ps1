# Despliegue Preview a Vercel (red corporativa: TLS y sin symlink de Windows).
# Uso:  powershell -File scripts/deployar-vercel.ps1
$ErrorActionPreference = "Stop"
$env:NODE_TLS_REJECT_UNAUTHORIZED = "0"
$env:npm_config_strict_ssl = "false"
Set-Location (Split-Path $PSScriptRoot -Parent)

$clave = $env:DEMO_CLAVE
if (-not $clave) { $clave = "jefe-prueba-2026" }

Write-Host "Login (si pide navegador, confirma el codigo de dispositivo)..."
npx --yes vercel@41.7.8 whoami
if ($LASTEXITCODE -ne 0) {
  npx --yes vercel@41.7.8 login
}

Write-Host "Desplegando Preview con clave de demo..."
npx --yes vercel@41.7.8 deploy --yes --confirm `
  --env "DEMO_CLAVE=$clave" `
  --env "SESION_SECRETA=$clave" `
  --env "SCRAPE_HEADLESS=1" `
  --env "SCRAPE_MANUAL_LOGIN=0"
Write-Host "DEMO_CLAVE=$clave"
