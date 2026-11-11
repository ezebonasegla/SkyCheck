from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class Leg:
    origin: str
    destination: str
    day: date


@dataclass(frozen=True)
class Trip:
    """Itinerario open-jaw: ida (outbound) + vuelta desde otra ciudad (inbound)."""

    outbound: Leg
    inbound: Leg

    @property
    def key(self) -> str:
        return (
            f"{self.outbound.origin}-{self.outbound.destination}-{self.outbound.day.isoformat()}"
            f"_{self.inbound.origin}-{self.inbound.destination}-{self.inbound.day.isoformat()}"
        )

    @property
    def stay_days(self) -> int:
        return (self.inbound.day - self.outbound.day).days


@dataclass
class Offer:
    source: str
    trip: Trip
    price: float
    currency: str
    # True = incluye equipaje de mano, False = no incluye, None = no se pudo determinar
    carry_on: Optional[bool]
    url: str
    airline: str = ""
    details: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def carry_on_label(self) -> str:
        return {True: "sí", False: "no", None: "verificar"}[self.carry_on]
