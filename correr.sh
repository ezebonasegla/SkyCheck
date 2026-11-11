#!/usr/bin/env bash
# Corre SkyCheck una vez (Mac / Linux). Para programarlo todos los días a las 9:
#   crontab -e   y agregar la línea:
#   0 9 * * * /ruta/a/SkyCheck/correr.sh
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
  .venv/bin/python -m playwright install chromium
fi
mkdir -p data
echo "===== $(date '+%F %T') =====" >> data/skycheck.log
.venv/bin/python -m skycheck.main >> data/skycheck.log 2>&1
