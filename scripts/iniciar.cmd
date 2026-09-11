@echo off
REM Sobe um servidor estatico local e abre o simulador. Ctrl+C para parar.
REM A pagina usa modulos ES, entao abrir o index.html direto (file://) nao funciona.
cd /d "%~dp0.."
start "" http://127.0.0.1:8765/
python -m http.server 8765 --bind 127.0.0.1
