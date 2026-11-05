@echo off
cd /d "%~dp0"
echo Motor de perfilamiento IA — instalacion en este computador
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\preparar-equipo.ps1"
echo.
if errorlevel 1 (
  echo La preparacion fallo. Revisa el mensaje de arriba.
  pause
  exit /b 1
)
echo.
echo Siguiente paso: scripts\iniciar.ps1
echo Luego abre Chrome en http://127.0.0.1:8000
pause
