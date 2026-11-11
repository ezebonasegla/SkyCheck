from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import Offer, Trip

SCHEMA = """
CREATE TABLE IF NOT EXISTS checks (
    source TEXT NOT NULL,
    trip_key TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    ok INTEGER NOT NULL,
    PRIMARY KEY (source, trip_key)
);
CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    found_at TEXT NOT NULL,
    source TEXT NOT NULL,
    trip_key TEXT NOT NULL,
    out_date TEXT NOT NULL,
    back_date TEXT NOT NULL,
    price REAL NOT NULL,
    currency TEXT NOT NULL,
    carry_on INTEGER,
    airline TEXT,
    url TEXT
);
CREATE INDEX IF NOT EXISTS offers_price ON offers(price);
"""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class Storage:
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.executescript(SCHEMA)

    def last_checked(self, source: str) -> dict[str, str]:
        rows = self.db.execute("SELECT trip_key, checked_at FROM checks WHERE source=?", (source,))
        return dict(rows.fetchall())

    def order_by_staleness(self, source: str, trips: list[Trip]) -> list[Trip]:
        """Primero las combinaciones nunca revisadas, luego las más viejas."""
        seen = self.last_checked(source)
        return sorted(trips, key=lambda t: seen.get(t.key, ""))

    def mark_checked(self, source: str, trip: Trip, ok: bool) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO checks VALUES (?,?,?,?)", (source, trip.key, _now(), int(ok))
        )
        self.db.commit()

    def best_price_ever(self, currency: str) -> Optional[float]:
        row = self.db.execute(
            "SELECT MIN(price) FROM offers WHERE currency=? AND (carry_on IS NULL OR carry_on=1)",
            (currency,),
        ).fetchone()
        return row[0]

    def save(self, offer: Offer) -> None:
        self.db.execute(
            "INSERT INTO offers (found_at, source, trip_key, out_date, back_date, price, currency,"
            " carry_on, airline, url) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                _now(), offer.source, offer.trip.key, offer.trip.outbound.day.isoformat(),
                offer.trip.inbound.day.isoformat(), offer.price, offer.currency,
                None if offer.carry_on is None else int(offer.carry_on), offer.airline, offer.url,
            ),
        )
        self.db.commit()

    def recent_best(self, currency: str, days: int = 7, limit: int = 10) -> list[tuple]:
        """Mejores precios vistos en los últimos `days` días (uno por combinación+fuente)."""
        return self.db.execute(
            """
            SELECT source, out_date, back_date, MIN(price) AS p, currency, carry_on, airline, url
            FROM offers
            WHERE currency=? AND (carry_on IS NULL OR carry_on=1)
              AND found_at >= datetime('now', ?)
            GROUP BY source, trip_key
            ORDER BY p ASC LIMIT ?
            """,
            (currency, f"-{days} days", limit),
        ).fetchall()
