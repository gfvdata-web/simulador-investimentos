@echo off
REM Sobe o simulador e abre o navegador. Ctrl+C para parar.
cd /d "%~dp0.."
python -m backend.app %*
pause
