@echo off
REM Roda o coletor na mao, fora da automacao do GitHub Actions.
cd /d "%~dp0.."
python coletor/atualizar.py %*
pause
