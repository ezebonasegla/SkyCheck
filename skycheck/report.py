from __future__ import annotations

import html as _html
from datetime import date

from .links import all_links
from .models import Offer

SITE_NAMES = {
    "google_flights": "Google Flights", "despegar": "Despegar", "turismocity": "Turismocity",
    "skyscanner": "Skyscanner", "cheapoair": "CheapOair",
}


def _fmt_day(d: date) -> str:
    dias = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
    return f"{dias[d.weekday()]} {d.strftime('%d/%m')}"


def _price(o: Offer) -> str:
    return f"{o.currency} {o.price:,.0f}".replace(",", ".")


def build_report(cfg: dict, best: list[Offer], alerts: list[Offer], stats: dict,
                 errors: dict[str, str]) -> tuple[str, str, str]:
    """Devuelve (asunto, texto plano/markdown, html)."""
    it = cfg["itinerary"]
    route = (f"{it['outbound']['origin']}→{it['outbound']['destination']} / "
             f"{it['inbound']['origin']}→{it['inbound']['destination']}")
    top = best[0] if best else None
    subject = f"SkyCheck {route}: " + (f"desde {_price(top)}" if top else "sin resultados hoy")
    if alerts:
        subject = "🔔 " + subject

    lines = [f"# SkyCheck — {route}", "",
             f"Ventana {cfg['window']['start']} a {cfg['window']['end']}, "
             f"{cfg['stay_days']['min']}–{cfg['stay_days']['max']} días, "
             f"{'con' if cfg.get('require_carry_on') else 'sin exigir'} equipaje de mano.", ""]
    if alerts:
        lines += ["## 🔔 Alertas", ""]
        lines += [f"- **{_price(o)}** {_fmt_day(o.trip.outbound.day)} → {_fmt_day(o.trip.inbound.day)} "
                  f"({o.trip.stay_days} días) · {SITE_NAMES.get(o.source, o.source)} · {o.url}"
                  for o in alerts]
        lines.append("")
    lines += ["## Mejores opciones de hoy", "",
              "| # | Precio | Ida | Vuelta | Días | Fuente | Aerolínea | Carry-on | Link |",
              "|---|---|---|---|---|---|---|---|---|"]
    for n, o in enumerate(best, 1):
        lines.append(
            f"| {n} | {_price(o)} | {_fmt_day(o.trip.outbound.day)} | {_fmt_day(o.trip.inbound.day)} | "
            f"{o.trip.stay_days} | {SITE_NAMES.get(o.source, o.source)} | {o.airline or '-'} | "
            f"{o.carry_on_label} | [ver]({o.url}) |")
    if not best:
        lines.append("| - | sin resultados | | | | | | | |")
    if top:
        lines += ["", "### Comparar la mejor fecha en todos los sitios", ""]
        lines += [f"- {SITE_NAMES[s]}: {u}" for s, u in all_links(top.trip, cfg).items()]
    lines += ["", "## Estado de las fuentes", ""]
    for src, st in stats.items():
        err = f" — ⚠️ {errors[src]}" if src in errors else ""
        lines.append(f"- {SITE_NAMES.get(src, src)}: {st['searched']} búsquedas, "
                     f"{st['offers']} tarifas{err}")
    lines += ["", "_“Carry-on: verificar” = el sitio no dice si incluye equipaje de mano; "
              "revisalo antes de comprar. Los precios cambian minuto a minuto._"]
    text = "\n".join(lines)
    return subject, text, _to_html(subject, alerts, best, stats, errors, cfg)


def _to_html(subject, alerts, best, stats, errors, cfg) -> str:
    e = _html.escape
    rows = "".join(
        f"<tr><td><b>{e(_price(o))}</b></td><td>{e(_fmt_day(o.trip.outbound.day))}</td>"
        f"<td>{e(_fmt_day(o.trip.inbound.day))}</td><td>{o.trip.stay_days}</td>"
        f"<td>{e(SITE_NAMES.get(o.source, o.source))}</td><td>{e(o.airline or '-')}</td>"
        f"<td>{e(o.carry_on_label)}</td><td><a href=\"{e(o.url)}\">ver</a></td></tr>"
        for o in best) or "<tr><td colspan=8>Sin resultados hoy</td></tr>"
    alert_html = ""
    if alerts:
        items = "".join(
            f"<li><b>{e(_price(o))}</b> {e(_fmt_day(o.trip.outbound.day))} → "
            f"{e(_fmt_day(o.trip.inbound.day))} · {e(SITE_NAMES.get(o.source, o.source))} · "
            f"<a href=\"{e(o.url)}\">ver</a></li>" for o in alerts)
        alert_html = f"<h3>🔔 Alertas</h3><ul>{items}</ul>"
    links = ""
    if best:
        links = "<h3>Comparar la mejor fecha en todos los sitios</h3><ul>" + "".join(
            f"<li><a href=\"{e(u)}\">{e(SITE_NAMES[s])}</a></li>"
            for s, u in all_links(best[0].trip, cfg).items()) + "</ul>"
    status = "".join(
        f"<li>{e(SITE_NAMES.get(s, s))}: {st['searched']} búsquedas, {st['offers']} tarifas"
        + (f" — ⚠️ {e(errors[s])}" if s in errors else "") + "</li>"
        for s, st in stats.items())
    return f"""<html><body style="font-family:Arial,sans-serif">
<h2>{e(subject)}</h2>
<p>Ida y vuelta entre {e(str(cfg['window']['start']))} y {e(str(cfg['window']['end']))},
{cfg['stay_days']['min']}–{cfg['stay_days']['max']} días,
{'con' if cfg.get('require_carry_on') else 'sin exigir'} equipaje de mano.</p>
{alert_html}
<h3>Mejores opciones de hoy</h3>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">
<tr><th>Precio</th><th>Ida</th><th>Vuelta</th><th>Días</th><th>Fuente</th><th>Aerolínea</th><th>Carry-on</th><th>Link</th></tr>
{rows}</table>
{links}
<h3>Estado de las fuentes</h3><ul>{status}</ul>
<p style="color:#666;font-size:12px">"Carry-on: verificar" = el sitio no aclara si incluye equipaje de mano; revisalo antes de comprar.</p>
</body></html>"""
