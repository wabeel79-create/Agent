@echo off
chcp 65001 >nul
cd /d "%~dp0"
.venv\Scripts\python -m app.admin sauvegarder
echo Copiez regulierement le dossier "sauvegardes" sur un disque externe.
pause
