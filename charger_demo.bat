@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Ajout de 4 clients fictifs de demonstration (marques "(demo)")...
.venv\Scripts\python -m app.demo
echo Termine. Ils se suppriment depuis leur fiche (onglet Fiche).
pause
