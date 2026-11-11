from __future__ import annotations

from ..models import Offer, Trip


class ProviderUnavailable(Exception):
    """La fuente no se puede usar en esta ejecución (falta API key, bloqueo, etc.)."""


class ProviderBlocked(ProviderUnavailable):
    """El sitio mostró captcha o bloqueó el acceso: se lo deja descansar unos días."""


class Provider:
    name: str = "base"

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.budget = int((cfg.get("providers", {}).get(self.name) or {}).get("max_searches_per_run", 10))

    def search(self, trip: Trip) -> list[Offer]:
        raise NotImplementedError

    def close(self) -> None:
        pass
