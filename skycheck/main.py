"""Punto de entrada: python -m skycheck.main [--config config.yaml] [--dry-run] [--no-email]"""
from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path

from .config import load_config
from .models import Offer
from .notify import send_email
from .providers import build_providers
from .providers.base import ProviderBlocked, ProviderUnavailable
from .report import build_report
from .storage import Storage
from .trips import generate_trips


def filter_offers(offers: list[Offer], cfg: dict) -> list[Offer]:
    """Aplica la regla de equipaje de mano y se queda con la más barata por fuente+fechas."""
    if cfg.get("require_carry_on"):
        offers = [o for o in offers if o.carry_on is not False]
    best: dict[tuple, Offer] = {}
    for o in offers:
        k = (o.source, o.trip.key, o.currency)
        # a igual precio, preferir la que confirma carry-on
        if k not in best or (o.price, o.carry_on is not True) < (best[k].price, best[k].carry_on is not True):
            best[k] = o
    return sorted(best.values(), key=lambda o: (o.price, o.carry_on is not True))


def pick_alerts(offers: list[Offer], cfg: dict, previous_min: float | None) -> list[Offer]:
    cur = cfg.get("currency", "USD")
    a = cfg.get("alerts", {})
    out = []
    for o in offers:
        if o.currency != cur:
            continue
        below = a.get("max_price") is not None and o.price <= float(a["max_price"])
        record = a.get("notify_new_minimum", True) and previous_min is not None and o.price < previous_min
        if below or record:
            out.append(o)
    return out[:5]


def load_dotenv(path: str | Path = ".env") -> None:
    """Carga variables de un archivo .env (para correrlo en tu compu)."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def run(cfg: dict, send: bool = True, dry_run: bool = False,
        only: list[str] | None = None, skip: list[str] | None = None) -> int:
    trips = generate_trips(cfg)
    print(f"{len(trips)} combinaciones de fechas posibles")
    if dry_run:
        for t in trips[:10]:
            print(" ", t.key, f"({t.stay_days} días)")
        return 0

    store = Storage(cfg.get("database", "data/history.sqlite"))
    cur = cfg.get("currency", "USD")
    previous_min = store.best_price_ever(cur)

    all_offers: list[Offer] = []
    stats: dict[str, dict] = {}
    errors: dict[str, str] = {}
    cooldown_h = float(cfg.get("block_cooldown_hours", 48))
    for prov in build_providers(cfg):
        if (only and prov.name not in only) or (skip and prov.name in skip):
            continue
        stats[prov.name] = {"searched": 0, "offers": 0}
        since = store.in_cooldown(prov.name, cooldown_h)
        if since:
            errors[prov.name] = f"en pausa: bloqueó el acceso el {since} UTC (se reintenta en {cooldown_h:.0f} h)"
            print(f"[{prov.name}] {errors[prov.name]}")
            continue
        queue = store.order_by_staleness(prov.name, trips)[: prov.budget]
        print(f"[{prov.name}] {len(queue)} búsquedas")
        try:
            for trip in queue:
                try:
                    found = prov.search(trip)
                    store.mark_checked(prov.name, trip, True)
                except ProviderUnavailable:
                    raise
                except Exception as e:  # una búsqueda falla, seguimos con la próxima
                    store.mark_checked(prov.name, trip, False)
                    errors[prov.name] = f"{type(e).__name__}: {str(e)[:120]}"
                    print(f"  {trip.key}: error {errors[prov.name]}")
                    continue
                stats[prov.name]["searched"] += 1
                store.clear_block(prov.name)
                kept = filter_offers(found, cfg)
                stats[prov.name]["offers"] += len(kept)
                for o in kept[:3]:
                    store.save(o)
                all_offers += kept
                print(f"  {trip.key}: {len(kept)} tarifas" + (f", mín {kept[0].currency} {kept[0].price:.0f}" if kept else ""))
        except ProviderBlocked as e:
            store.mark_blocked(prov.name, str(e))
            errors[prov.name] = f"{e} — se pausa {cooldown_h:.0f} h"
            print(f"[{prov.name}] {errors[prov.name]}")
        except ProviderUnavailable as e:
            errors[prov.name] = str(e)
            print(f"[{prov.name}] no disponible: {e}")
        except Exception as e:
            errors[prov.name] = f"{type(e).__name__}: {str(e)[:120]}"
            traceback.print_exc()
        finally:
            prov.close()

    today = filter_offers(all_offers, cfg)
    alerts = pick_alerts(today, cfg, previous_min)
    top_n = int(cfg.get("alerts", {}).get("top_n", 10))
    subject, text, html = build_report(cfg, today[:top_n], alerts, stats, errors)

    report_file = Path(cfg.get("report_file", "data/ultimo_reporte.md"))
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(text, encoding="utf-8")
    print("\n" + text)

    if send:
        try:
            send_email(subject, text, html)
        except Exception as e:
            print(f"[email] error enviando: {e}")
            return 1
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="SkyCheck: buscador diario de vuelos baratos")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--dry-run", action="store_true", help="solo lista las combinaciones de fechas")
    ap.add_argument("--no-email", action="store_true", help="no enviar el mail")
    ap.add_argument("--only", help="solo estas fuentes, separadas por coma (ej. google_flights)")
    ap.add_argument("--skip", help="saltear estas fuentes, separadas por coma")
    args = ap.parse_args(argv)
    load_dotenv()
    split = lambda v: [x.strip() for x in v.split(",") if x.strip()] if v else None
    return run(load_config(args.config), send=not args.no_email, dry_run=args.dry_run,
               only=split(args.only), skip=split(args.skip))


if __name__ == "__main__":
    sys.exit(main())
