"""Google Flights a través de SerpApi (https://serpapi.com/google-flights-api).

Es la fuente más estable: devuelve JSON, soporta multi-destino y el parámetro
`bags=1` hace que el precio incluya el equipaje de mano.
Requiere la variable de entorno SERPAPI_KEY (plan gratis: 100 búsquedas/mes).
"""
from __future__ import annotations

import json
import os

import requests

from ..baggage import detect_carry_on
from ..links import build_link
from ..models import Offer, Trip
from .base import Provider, ProviderUnavailable

# Google usa aeropuertos, no códigos de ciudad.
CITY_AIRPORTS = {"BUE": "EZE,AEP", "MDE": "MDE", "CTG": "CTG"}


def _airports(code: str) -> str:
    return CITY_AIRPORTS.get(code.upper(), code.upper())


class GoogleFlightsProvider(Provider):
    name = "google_flights"
    endpoint = "https://serpapi.com/search.json"

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.api_key = os.environ.get("SERPAPI_KEY", "")

    def params(self, trip: Trip) -> dict:
        legs = [
            {"departure_id": _airports(trip.outbound.origin),
             "arrival_id": _airports(trip.outbound.destination),
             "date": trip.outbound.day.isoformat()},
            {"departure_id": _airports(trip.inbound.origin),
             "arrival_id": _airports(trip.inbound.destination),
             "date": trip.inbound.day.isoformat()},
        ]
        p = {
            "engine": "google_flights",
            "type": "3",  # multi-city
            "multi_city_json": json.dumps(legs),
            "currency": self.cfg.get("currency", "USD"),
            "hl": "es",
            "gl": "ar",
            "adults": self.cfg.get("passengers", {}).get("adults", 1),
            "api_key": self.api_key,
        }
        if self.cfg.get("require_carry_on"):
            p["bags"] = 1  # precio con 1 carry-on incluido
        return p

    def search(self, trip: Trip) -> list[Offer]:
        if not self.api_key:
            raise ProviderUnavailable("falta SERPAPI_KEY")
        r = requests.get(self.endpoint, params=self.params(trip), timeout=60)
        if r.status_code == 401:
            raise ProviderUnavailable("SERPAPI_KEY inválida")
        if r.status_code == 429:
            raise ProviderUnavailable("se agotó la cuota de SerpApi")
        r.raise_for_status()
        return self.parse(r.json(), trip)

    def parse(self, data: dict, trip: Trip) -> list[Offer]:
        if data.get("error"):
            return []
        cur = self.cfg.get("currency", "USD")
        link = data.get("search_metadata", {}).get("google_flights_url") or build_link(
            "google_flights", trip, currency=cur)
        offers = []
        for item in (data.get("best_flights") or []) + (data.get("other_flights") or []):
            price = item.get("price")
            if not price:
                continue
            flights = item.get("flights") or []
            texts = list(item.get("extensions") or [])
            for f in flights:
                texts += f.get("extensions") or []
            carry = detect_carry_on(" | ".join(texts))
            if carry is None and self.cfg.get("require_carry_on"):
                # Pedimos bags=1: Google ya sumó el costo del carry-on al precio.
                carry = True
            airlines = sorted({f.get("airline", "") for f in flights if f.get("airline")})
            stops = max(len(flights) - 1, 0)
            offers.append(Offer(
                source=self.name, trip=trip, price=float(price), currency=cur,
                carry_on=carry, url=link, airline=", ".join(airlines),
                details=f"ida: {stops} escala(s) · {item.get('total_duration', '?')} min",
            ))
        return offers
