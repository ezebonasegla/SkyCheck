# SkyCheck ✈️

Bot que busca **todos los días** vuelos baratos para un viaje multi-destino:

- **Ida:** Buenos Aires (EZE/AEP) → **Cartagena**
- **Vuelta:** **Medellín** → Buenos Aires
- Viaje de **11 a 13 días**, todo entre **marzo y abril de 2027** (147 combinaciones de fechas)
- **Con equipaje de mano** (carry-on): las tarifas que dicen "sin equipaje de mano" se descartan
- Fuentes: **Google Flights** (vía SerpApi), **Despegar**, **Turismocity**, **Skyscanner**, **CheapOair**
- Te manda **un resumen por email** con las mejores opciones y links para comprar, y te
  avisa (🔔 en el asunto) cuando hay un precio por debajo de tu límite o un nuevo mínimo histórico.

Todo se configura en [`config.yaml`](config.yaml) (rutas, fechas, días, precio de alerta, equipaje, fuentes).

## Cómo funciona

1. Genera todas las combinaciones ida/vuelta válidas.
2. Cada fuente tiene un presupuesto de búsquedas por día. Se revisan primero las fechas
   que hace más tiempo que no se miran, así que en unos días se cubre todo el rango y
   después se va actualizando en rotación.
3. Filtra por equipaje de mano, guarda el historial en `data/history.sqlite` y arma el
   reporte (`data/ultimo_reporte.md`).
4. Envía el resumen por email.

## ¿Dónde corre? Dos opciones

| | En tu compu (recomendado) | En GitHub Actions |
|---|---|---|
| Fuentes | las 5 | solo Google Flights |
| Requisito | la compu prendida (si estaba apagada, corre al prenderla) | nada |
| Por qué | Despegar, Turismocity, Skyscanner y CheapOair bloquean las IPs de servidores como los de GitHub, pero no a una conexión hogareña que hace unas pocas búsquedas por día | |

Usá **una sola** para no recibir dos mails: si programás tu compu, desactivá el
workflow en GitHub (*Actions → SkyCheck diario → ⋯ → Disable workflow*).

### Para no ser bloqueado
- Pocas búsquedas: 5 por sitio por día, con 20–60 s de pausa entre una y otra.
- Si un sitio pide captcha o bloquea, el bot **lo deja en pausa 48 h** en vez de
  insistir (`block_cooldown_hours` en `config.yaml`). El mail lo indica.
- No usa servicios para resolver captchas ni proxies: si un sitio igual bloquea,
  queda Google Flights y los links directos del mail.

## Puesta en marcha (una sola vez)

### 1. Email (Gmail)
1. En tu cuenta de Google activá la verificación en 2 pasos.
2. Creá una **contraseña de aplicación** en <https://myaccount.google.com/apppasswords>.
3. En GitHub: *Settings → Secrets and variables → Actions → New repository secret* y creá:

| Secret | Valor |
|---|---|
| `EMAIL_TO` | el mail donde querés recibir el resumen |
| `SMTP_USER` | el Gmail que envía (puede ser el mismo) |
| `SMTP_PASSWORD` | la contraseña de aplicación de 16 letras |

> El destinatario va como secreto y no en el código para que tu mail no quede público.

### 2. Google Flights (recomendado)
Creá una cuenta en <https://serpapi.com> (plan gratis = 100 búsquedas/mes) y guardá la
API key como secreto `SERPAPI_KEY`. Con el plan gratis el bot hace 3 búsquedas por día;
si pagás un plan más grande subí `max_searches_per_run` en `config.yaml`.
Google Flights calcula el precio **con el carry-on incluido** (`bags=1`).

### 3a. Programarlo en tu compu (Windows)
1. Instalá Python 3 desde <https://www.python.org/downloads/> (tildá *Add python.exe to PATH*).
2. Descargá el repo (*Code → Download ZIP*) y descomprimilo, por ejemplo en `C:\SkyCheck`.
3. Copiá `.env.example` como `.env` y completá tu mail, la contraseña de aplicación y la
   `SERPAPI_KEY`. (`.env` queda solo en tu compu.)
4. Doble clic en `correr.bat` una vez para probar (la primera vez instala todo; tarda
   unos minutos). Vas a recibir el mail y el detalle queda en `data\skycheck.log`.
5. Clic derecho en `instalar_tarea_windows.ps1` → **Ejecutar con PowerShell**. Queda
   programado todos los días a las 9:00.

En Mac/Linux: lo mismo con `./correr.sh`, y programarlo con `crontab -e` agregando
`0 9 * * * /ruta/a/SkyCheck/correr.sh`.

### 3b. O dejarlo en GitHub Actions
En la pestaña **Actions** → *SkyCheck diario* → **Run workflow**. En unos minutos te
llega el mail (solo con Google Flights).

## Comandos

```bash
python -m skycheck.main                       # busca y manda el mail
python -m skycheck.main --no-email            # solo muestra el reporte
python -m skycheck.main --only google_flights # solo algunas fuentes
python -m skycheck.main --skip skyscanner     # saltear alguna
python -m skycheck.main --dry-run             # lista las combinaciones de fechas
python -m pytest                              # tests
```

## Limitaciones (importante)

- **Despegar, Turismocity, Skyscanner y CheapOair no tienen API pública.** El bot los
  lee con un navegador automatizado (Playwright). Estos sitios tienen protección
  anti-bots y aun desde tu compu pueden pedir captcha alguna vez; en ese caso el sitio
  queda en pausa, el mail lo indica en "Estado de las fuentes" y el resto sigue
  funcionando. Si cambian el diseño de su página hay que ajustar los selectores en
  `skycheck/providers/scraper.py` (o `card_selector` en `config.yaml`).
- Revisá los términos de uso de cada sitio; el bot hace pocas búsquedas por día y con
  pausas largas entre una y otra.
- **Equipaje de mano:** se detecta por el texto de cada tarifa. Si el sitio no lo aclara
  aparece como "verificar" — revisalo antes de comprar. Ojo con las tarifas *light / basic*
  de JetSMART, Avianca, LATAM, etc., que solo incluyen un artículo personal (mochila).
- Si un sitio muestra precios en pesos, se informan en ARS y no disparan la alerta en USD.
- Siempre hay un bloque de **links directos** a la mejor fecha en los 5 sitios para
  comparar a mano.
