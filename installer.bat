@echo off
chcp 65001 >nul
title Installation Kapsi-Q
cd /d "%~dp0"
echo ============================================
echo   Installation de Kapsi-Q - SmartCell Technologies
echo ============================================
set PY=
where py >nul 2>nul && set PY=py -3
if not defined PY ( where python >nul 2>nul && set PY=python )
if not defined PY (
  echo.
  echo  Python n'est pas installe sur ce poste.
  echo  1. Installez Python 3.12 64 bits depuis https://www.python.org/downloads/
  echo  2. Cochez "Add python.exe to PATH" pendant l'installation.
  echo  3. Relancez installer.bat
  start "" https://www.python.org/downloads/
  pause
  exit /b 1
)
echo [1/4] Creation de l'environnement isole (.venv)...
if not exist .venv %PY% -m venv .venv || goto :err
echo [2/4] Installation des composants...
if exist wheels (
  .venv\Scripts\python -m pip install -q --no-index --find-links wheels -r requirements.txt || goto :online
) else (
  goto :online
)
goto :cfg
:online
echo      (installation depuis Internet)
.venv\Scripts\python -m pip install -q -r requirements.txt || goto :err
:cfg
echo [3/4] Configuration...
if not exist kapsi.env copy /y kapsi.env.bimcot kapsi.env >nul
echo [4/4] Raccourci sur le bureau...
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Kapsi-Q.lnk');$s.TargetPath='%~dp0demarrer_kapsi.bat';$s.WorkingDirectory='%~dp0';$s.IconLocation='%~dp0app\static\icons\kapsi.ico';$s.Save()" >nul 2>nul
.venv\Scripts\python -m app.admin info
echo.
echo  Installation terminee. Double-cliquez sur "Kapsi-Q" sur le bureau
echo  ou sur demarrer_kapsi.bat pour lancer l'application.
pause
exit /b 0
:err
echo.
echo  ERREUR pendant l'installation. Envoyez une capture de cet ecran au support SmartCell.
pause
exit /b 1
