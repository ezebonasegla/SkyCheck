"""Links de búsqueda multi-destino para cada sitio.

Los formatos de URL de los sitios cambian cada tanto. Si alguno deja de
funcionar, se puede pisar desde config.yaml con `providers.<sitio>.url_template`
usando los campos: {o1} {d1} {o2} {d2} {date1} {date2} (YYYY-MM-DD),
{date1_compact} {date2_compact} (YYMMDD), {date1_us} {date2_us} (MM/DD/YYYY),
{adults} {currency} y sus versiones en minúscula {o1_l} {d1_l} {o2_l} {d2_l}.
"""
from __future__ import annotations

from .models import Trip

TEMPLATES = {
    "despegar": (
        "https://www.despegar.com.ar/shop/flights/results/multipledestinations/"
        "{o1},{o2}/{d1},{d2}/{date1},{date2}/{adults}/0/0/NA/NA/NA/NA/NA"
    ),
    "turismocity": (
        "https://www.turismocity.com.ar/vuelos/resultados?type=multi"
        "&from1={o1}&to1={d1}&date1={date1}&from2={o2}&to2={d2}&date2={date2}"
        "&adults={adults}&children=0&infants=0&cabin=Y"
    ),
    "skyscanner": (
        "https://www.skyscanner.com.ar/transport/d/{o1_l}/{date1}/{d1_l}/"
        "{o2_l}/{date2}/{d2_l}/?adultsv2={adults}&cabinclass=economy&childrenv2="
        "&currency={currency}"
    ),
    "cheapoair": (
        "https://www.cheapoair.com/air/listing?&d1={o1}&r1={d1}&dt1={date1_us}"
        "&d2={o2}&r2={d2}&dt2={date2_us}&tripType=MULTICITY&cl=ECONOMY"
        "&ad={adults}&se=0&ch=0&infl=0&infs=0"
    ),
    "google_flights": (
        "https://www.google.com/travel/flights?hl=es&curr={currency}&q="
        "Flights%20from%20{o1}%20to%20{d1}%20on%20{date1}%20and%20from%20{o2}"
        "%20to%20{d2}%20on%20{date2}"
    ),
}


def fields(trip: Trip, adults: int = 1, currency: str = "USD") -> dict:
    o, i = trip.outbound, trip.inbound
    f = {
        "o1": o.origin, "d1": o.destination, "o2": i.origin, "d2": i.destination,
        "date1": o.day.isoformat(), "date2": i.day.isoformat(),
        "date1_compact": o.day.strftime("%y%m%d"), "date2_compact": i.day.strftime("%y%m%d"),
        "date1_us": o.day.strftime("%m/%d/%Y"), "date2_us": i.day.strftime("%m/%d/%Y"),
        "adults": adults, "currency": currency,
    }
    for k in ("o1", "d1", "o2", "d2"):
        f[f"{k}_l"] = f[k].lower()
    return f


def build_link(site: str, trip: Trip, adults: int = 1, currency: str = "USD",
               template: str | None = None) -> str:
    tpl = template or TEMPLATES[site]
    return tpl.format(**fields(trip, adults, currency))


def all_links(trip: Trip, cfg: dict) -> dict[str, str]:
    adults = cfg.get("passengers", {}).get("adults", 1)
    cur = cfg.get("currency", "USD")
    provs = cfg.get("providers", {})
    return {
        site: build_link(site, trip, adults, cur, (provs.get(site) or {}).get("url_template"))
        for site in TEMPLATES
    }
