@echo off
rem Abre Kreix. La primera vez crea el entorno e instala lo necesario (hace falta Python 3.11 o superior).
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Preparando Kreix la primera vez, puede tardar un minuto...
  py -3 -m venv .venv 2>nul || python -m venv .venv
  if errorlevel 1 (
    echo No se encontro Python 3.11 o superior. Instalalo desde https://www.python.org y vuelve a abrir este archivo.
    pause
    exit /b 1
  )
  ".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt
  if errorlevel 1 (
    echo No se pudieron instalar las dependencias. Comprueba tu conexion e intentalo de nuevo.
    pause
    exit /b 1
  )
)
start "" ".venv\Scripts\pythonw.exe" main.py %*
