@echo off
chcp 65001 >nul
title Kapsi-Q
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe call installer.bat
set PORT=8000
if exist kapsi.env for /f "usebackq tokens=1,2 delims==" %%a in ("kapsi.env") do if "%%a"=="KAPSI_PORT" set PORT=%%b
echo.
echo   Kapsi-Q est en cours d'execution.
echo   Sur ce poste : http://localhost:%PORT%
echo   Sur le reseau (autres PC, iPhone) : http://ADRESSE-IP-DE-CE-PC:%PORT%  (commande ipconfig)
echo   Ne fermez pas cette fenetre pendant l'utilisation.
echo.
start "" http://localhost:%PORT%
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port %PORT%
pause
