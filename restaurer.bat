@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Sauvegardes disponibles :
.venv\Scripts\python -m app.admin liste
echo.
echo Arretez Kapsi-Q (fermez sa fenetre) avant de restaurer.
set /p F=Nom du fichier a restaurer (ex. kapsi_q_20261201_180000.db) : 
.venv\Scripts\python -m app.admin restaurer "sauvegardes\%F%"
pause
