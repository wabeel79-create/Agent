@echo off
chcp 65001 >nul
title Kapsi-Q
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
echo Installation des dependances...
%PY% -m pip install -q -r requirements.txt
if not exist data\kapsi_q.db (
  echo Chargement des donnees de demonstration...
  %PY% -m app.demo
)
echo.
echo  Kapsi-Q demarre : ouvrez http://localhost:8000
echo  Sur iPhone (meme Wi-Fi) : http://ADRESSE-IP-DU-PC:8000  (voir ipconfig)
echo  Fermez cette fenetre pour arreter.
echo.
start "" http://localhost:8000
%PY% -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
