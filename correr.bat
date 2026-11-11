@echo off
REM Corre SkyCheck una vez (Windows). Lo usa la tarea programada.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  .venv\Scripts\python -m pip install -q -r requirements.txt
  .venv\Scripts\python -m playwright install chromium
)
.venv\Scripts\python -m skycheck.main >> data\skycheck.log 2>&1
