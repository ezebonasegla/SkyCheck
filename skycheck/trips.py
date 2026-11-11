from __future__ import annotations

from datetime import date, timedelta
from typing import Iterator

from .models import Leg, Trip


def generate_trips(cfg: dict) -> list[Trip]:
    """Todas las combinaciones ida/vuelta dentro de la ventana y la duración pedida."""
    it = cfg["itinerary"]
    start: date = _as_date(cfg["window"]["start"])
    end: date = _as_date(cfg["window"]["end"])
    smin, smax = int(cfg["stay_days"]["min"]), int(cfg["stay_days"]["max"])

    trips: list[Trip] = []
    for out_day in _days(start, end):
        for stay in range(smin, smax + 1):
            back = out_day + timedelta(days=stay)
            if back > end:
                continue
            trips.append(
                Trip(
                    Leg(it["outbound"]["origin"], it["outbound"]["destination"], out_day),
                    Leg(it["inbound"]["origin"], it["inbound"]["destination"], back),
                )
            )
    return trips


def _days(start: date, end: date) -> Iterator[date]:
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _as_date(v) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v))
