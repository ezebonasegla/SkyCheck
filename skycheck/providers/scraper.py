"""Scraping con navegador (Playwright) de Despegar, Turismocity, Skyscanner y CheapOair.

IMPORTANTE: estos sitios no tienen API pública y usan protección anti-bots
(captcha, bloqueos por IP). Este scraper es "best effort": abre la página de
resultados multi-destino, espera que carguen los precios y toma las tarjetas de
resultado. Si un sitio cambia su HTML o bloquea el acceso, se registra el error
y el bot sigue con las demás fuentes. Los selectores se pueden ajustar en
SITE_RULES o pisar desde config.yaml (`providers.<sitio>.card_selector`).
"""
from __future__ import annotations

import os
import random
import re
import sys
import time

from ..baggage import detect_carry_on
from ..links import build_link
from ..models import Offer, Trip
from .base import Provider, ProviderBlocked, ProviderUnavailable

SITE_RULES = {
    "despegar": {
        "card_selector": "cluster, .cluster-container, [class*='cluster'], [data-testid*='cluster']",
        "currency_hint": None,
    },
    "turismocity": {
        "card_selector": "[class*='result-card'], [class*='ResultCard'], [class*='flight-card'], [class*='itinerary']",
        "currency_hint": None,
    },
    "skyscanner": {
        "card_selector": "[class*='FlightsResults_dayViewItems'] > div, [class*='EcoTicketWrapper'], [data-testid*='ticket']",
        "currency_hint": None,
    },
    "cheapoair": {
        "card_selector": "[class*='contract'], [class*='trip-card'], [class*='listing-card'], [class*='fare-card']",
        "currency_hint": "USD",
    },
}
SCRAPER_SITES = list(SITE_RULES)

BLOCK_MARKERS = [
    "captcha", "are you a robot", "eres un robot", "verify you are human",
    "access denied", "acceso denegado", "px-captcha", "unusual traffic",
]

# "US$ 1.234", "USD 1,234", "$ 1.234.567", "ARS 1.234.567", "U$S 812"
PRICE_RE = re.compile(
    r"(US\$|U\$S|USD|ARS|AR\$|\$)\s?(\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,](\d{2}))?(?!\d)"
)


def parse_price(text: str) -> tuple[float, str] | None:
    """Devuelve (precio, moneda) del menor precio plausible del texto."""
    found = []
    for sym, num, cents in PRICE_RE.findall(text or ""):
        value = float(re.sub(r"[.,]", "", num)) + (float(cents) / 100 if cents else 0)
        cur = "USD" if sym in ("US$", "U$S", "USD") else ("ARS" if sym in ("ARS", "AR$") else "$")
        if value >= 50:  # filtra tasas sueltas, cuotas chicas, etc.
            found.append((value, cur))
    if not found:
        return None
    return min(found)


class ScraperProvider(Provider):
    def __init__(self, site: str, cfg: dict, browser=None):
        self.name = site
        super().__init__(cfg)
        self.site_cfg = cfg.get("providers", {}).get(site) or {}
        self.rules = {**SITE_RULES[site], **{k: v for k, v in self.site_cfg.items() if k in SITE_RULES[site]}}
        self._browser = browser
        self._own_pw = None
        self._context = None
        self._first = True

    def _ctx(self):
        if self._context is None:
            if self._browser is None:
                try:
                    from playwright.sync_api import sync_playwright
                except ImportError as e:  # pragma: no cover
                    raise ProviderUnavailable("playwright no está instalado") from e
                self._own_pw = sync_playwright().start()
                self._browser = self._own_pw.chromium.launch(headless=self._headless())
            self._context = self._browser.new_context(
                locale="es-AR",
                timezone_id="America/Argentina/Buenos_Aires",
                viewport={"width": 1366, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
                ),
            )
        return self._context

    def _browser_cfg(self) -> dict:
        return self.cfg.get("browser") or {}

    def _headless(self) -> bool:
        env = os.environ.get("SKYCHECK_HEADLESS")
        if env is not None:
            return env.lower() in ("1", "true", "yes", "si")
        if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
            return True  # servidor sin pantalla (ej. GitHub Actions)
        return bool(self._browser_cfg().get("headless", True))

    def _is_blocked(self, page) -> bool:
        body = page.inner_text("body")[:20_000].lower()
        return any(m in body for m in BLOCK_MARKERS)

    def _wait_for_human(self, page) -> bool:
        """Con el navegador visible, si aparece un captcha avisa y espera a que
        lo resuelvas vos. Devuelve True si se destrabó."""
        minutes = float(self._browser_cfg().get("wait_for_captcha_minutes", 0))
        if self._headless() or minutes <= 0:
            return False
        print(f"\a[{self.name}] Apareció un captcha: resolvelo en la ventana del navegador "
              f"(espero hasta {minutes:.0f} min)...", flush=True)
        deadline = time.time() + minutes * 60
        while time.time() < deadline:
            page.wait_for_timeout(5_000)
            try:
                if not self._is_blocked(page):
                    print(f"[{self.name}] ¡Listo, sigo!", flush=True)
                    return True
            except Exception:
                pass  # la página está navegando
        return False

    def _pause(self):
        lo, hi = self.cfg.get("delay_between_searches", [20, 60])
        if not self._first:
            time.sleep(random.uniform(lo, hi))
        self._first = False

    def search(self, trip: Trip) -> list[Offer]:
        self._pause()
        cur = self.cfg.get("currency", "USD")
        url = build_link(self.name, trip, self.cfg.get("passengers", {}).get("adults", 1),
                         cur, self.site_cfg.get("url_template"))
        page = self._ctx().new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            try:
                page.wait_for_selector(self.rules["card_selector"], timeout=45_000)
            except Exception:
                pass
            page.wait_for_timeout(4_000)
            if self._is_blocked(page):
                if not self._wait_for_human(page):
                    raise ProviderBlocked(f"{self.name} pidió captcha / bloqueó el acceso")
                try:
                    page.wait_for_selector(self.rules["card_selector"], timeout=45_000)
                except Exception:
                    pass

            cards = page.query_selector_all(self.rules["card_selector"])
            texts = [c.inner_text() for c in cards[:30]]
            return self.parse_cards(texts, trip, url)
        finally:
            page.close()

    def parse_cards(self, texts: list[str], trip: Trip, url: str) -> list[Offer]:
        offers = []
        for text in texts:
            parsed = parse_price(text)
            if not parsed:
                continue
            price, cur = parsed
            if cur == "$":
                cur = self.rules.get("currency_hint") or self.cfg.get("currency", "USD")
            offers.append(Offer(
                source=self.name, trip=trip, price=price, currency=cur,
                carry_on=detect_carry_on(text), url=url,
                airline=_guess_airline(text), details=" ".join(text.split())[:160],
            ))
        return offers

    def close(self) -> None:
        try:
            if self._context:
                self._context.close()
            if self._own_pw:
                self._browser.close()
                self._own_pw.stop()
        except Exception:
            pass


AIRLINES = ["Avianca", "LATAM", "Copa", "Aerolíneas Argentinas", "JetSMART", "Flybondi",
            "Wingo", "Arajet", "American", "GOL", "Sky", "Viva", "Iberia", "Aeroméxico"]


def _guess_airline(text: str) -> str:
    low = text.lower()
    return ", ".join(a for a in AIRLINES if a.lower() in low)
