from .base import Provider
from .google_flights import GoogleFlightsProvider
from .scraper import SCRAPER_SITES, ScraperProvider


def build_providers(cfg: dict, browser=None) -> list[Provider]:
    out: list[Provider] = []
    pcfg = cfg.get("providers", {})
    if (pcfg.get("google_flights") or {}).get("enabled"):
        out.append(GoogleFlightsProvider(cfg))
    for site in SCRAPER_SITES:
        if (pcfg.get(site) or {}).get("enabled"):
            out.append(ScraperProvider(site, cfg, browser))
    return out
