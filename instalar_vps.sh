#!/usr/bin/env bash
# Instala SkyCheck en un VPS Linux (Ubuntu/Debian) y lo programa con cron.
# Uso (dentro de la carpeta del repo):
#   cp .env.example .env && nano .env     # completar mail, contraseña, SERPAPI_KEY
#   bash instalar_vps.sh                  # opcional: HORA=9 MINUTO=17 bash instalar_vps.sh
set -euo pipefail
cd "$(dirname "$0")"
DIR="$(pwd)"
HORA="${HORA:-9}"
MINUTO="${MINUTO:-17}"
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"

if [ ! -f .env ]; then
  echo "Falta el archivo .env: hacé  cp .env.example .env  y completalo."; exit 1
fi

# Python + venv
if ! python3 -m venv --help >/dev/null 2>&1 || ! python3 -c "import ensurepip" 2>/dev/null; then
  $SUDO apt-get update -y && $SUDO apt-get install -y python3-venv python3-pip
fi
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

# Navegador para Despegar / Turismocity / Skyscanner / CheapOair (+ librerías del sistema)
$SUDO .venv/bin/python -m playwright install-deps chromium
.venv/bin/python -m playwright install chromium

mkdir -p data
chmod +x correr.sh
chmod 600 .env

# Cron diario (reemplaza una entrada anterior de SkyCheck si existía)
LINE="$MINUTO $HORA * * * $DIR/correr.sh"
( crontab -l 2>/dev/null | grep -v "SkyCheck/correr.sh\|$DIR/correr.sh" || true; echo "$LINE" ) | crontab -

echo
echo "Listo. SkyCheck corre todos los días a las $(printf '%02d:%02d' "$HORA" "$MINUTO") (hora del VPS: $(date +%Z))."
echo "Para cambiar la hora:  HORA=8 MINUTO=30 bash instalar_vps.sh"
echo "Log:                   tail -f $DIR/data/skycheck.log"
echo "Probar ahora:          $DIR/correr.sh && tail -50 $DIR/data/skycheck.log"
