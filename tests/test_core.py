from datetime import date

from skycheck.baggage import detect_carry_on
from skycheck.config import load_config
from skycheck.links import all_links
from skycheck.main import filter_offers, pick_alerts
from skycheck.models import Leg, Offer, Trip
from skycheck.providers.google_flights import GoogleFlightsProvider
from skycheck.providers.scraper import ScraperProvider, parse_price
from skycheck.report import build_report
from skycheck.storage import Storage
from skycheck.trips import generate_trips

CFG = load_config("config.yaml")


def trip(d1=date(2027, 3, 5), d2=date(2027, 3, 17)):
    return Trip(Leg("BUE", "CTG", d1), Leg("MDE", "BUE", d2))


def test_trips_respect_window_and_stay():
    trips = generate_trips(CFG)
    assert len(trips) == 147
    assert all(11 <= t.stay_days <= 13 for t in trips)
    assert min(t.outbound.day for t in trips) == date(2027, 3, 1)
    assert max(t.inbound.day for t in trips) <= date(2027, 4, 30)
    assert all(t.outbound.origin == "BUE" and t.inbound.origin == "MDE" for t in trips)


def test_detect_carry_on():
    assert detect_carry_on("Tarifa Light · Sin equipaje de mano") is False
    assert detect_carry_on("Carry-on bags not included") is False
    assert detect_carry_on("Incluye equipaje de mano de 10 kg") is True
    assert detect_carry_on("1 free carry-on") is True
    assert detect_carry_on("Avianca · 1 escala") is None


def test_parse_price():
    assert parse_price("Precio final US$ 1.234 por adulto") == (1234.0, "USD")
    assert parse_price("ARS 1.234.567 o USD 980") == (980.0, "USD")
    assert parse_price("tasas $ 12") is None


def test_filter_drops_no_carry_on_and_dedupes():
    t = trip()
    offers = [
        Offer("despegar", t, 400, "USD", False, "u"),
        Offer("despegar", t, 500, "USD", None, "u"),
        Offer("despegar", t, 450, "USD", True, "u"),
        Offer("skyscanner", t, 480, "USD", True, "u"),
    ]
    kept = filter_offers(offers, CFG)
    assert [(o.source, o.price) for o in kept] == [("despegar", 450), ("skyscanner", 480)]


def test_alerts_threshold_and_record():
    t = trip()
    offers = [Offer("x", t, 650, "USD", True, "u"), Offer("x", t, 900, "USD", True, "u"),
              Offer("x", t, 100000, "ARS", True, "u")]
    assert [o.price for o in pick_alerts(offers, CFG, previous_min=None)] == [650]
    assert [o.price for o in pick_alerts(offers, CFG, previous_min=950)] == [650, 900]


def test_links_build_for_all_sites():
    links = all_links(trip(), CFG)
    assert set(links) == {"despegar", "turismocity", "skyscanner", "cheapoair", "google_flights"}
    assert "BUE,MDE/CTG,BUE/2027-03-05,2027-03-17" in links["despegar"]
    assert "/bue/2027-03-05/ctg/mde/2027-03-17/bue/" in links["skyscanner"]
    assert "dt1=03/05/2027" in links["cheapoair"]


def test_google_params_and_parse():
    p = GoogleFlightsProvider(CFG)
    params = p.params(trip())
    assert params["type"] == "3" and params["bags"] == 1
    assert '"departure_id": "EZE,AEP"' in params["multi_city_json"]
    data = {
        "search_metadata": {"google_flights_url": "https://g"},
        "best_flights": [
            {"price": 612, "flights": [{"airline": "Avianca", "extensions": []}], "total_duration": 600},
            {"price": 500, "flights": [{"airline": "X", "extensions": ["Carry-on bags not included"]}]},
        ],
    }
    offers = filter_offers(p.parse(data, trip()), CFG)
    assert [(o.price, o.airline, o.carry_on) for o in offers] == [(612.0, "Avianca", True)]


def test_scraper_parse_cards():
    sp = ScraperProvider("despegar", CFG)
    offers = sp.parse_cards(
        ["LATAM 1 escala US$ 702 Incluye equipaje de mano", "JetSMART US$ 450 Sin equipaje de mano", "nada"],
        trip(), "u")
    kept = filter_offers(offers, CFG)
    assert [(o.price, o.airline, o.carry_on) for o in kept] == [(702.0, "LATAM", True)]


def test_storage_rotation_and_report(tmp_path):
    st = Storage(tmp_path / "db.sqlite")
    trips = generate_trips(CFG)
    st.mark_checked("despegar", trips[0], True)
    assert st.order_by_staleness("despegar", trips)[-1] == trips[0]
    o = Offer("despegar", trips[0], 610, "USD", True, "https://x", "Avianca")
    st.save(o)
    assert st.best_price_ever("USD") == 610
    assert st.recent_best("USD")[0][3] == 610
    subject, text, html = build_report(CFG, [o], [o], {"despegar": {"searched": 1, "offers": 1}}, {})
    assert "USD 610" in subject and "Avianca" in text and "<table" in html


def test_block_cooldown(tmp_path):
    st = Storage(tmp_path / "db.sqlite")
    assert st.in_cooldown("skyscanner", 48) is None
    st.mark_blocked("skyscanner", "captcha")
    assert st.in_cooldown("skyscanner", 48)
    assert st.in_cooldown("skyscanner", 0) is None
    st.clear_block("skyscanner")
    assert st.in_cooldown("skyscanner", 48) is None


def test_blocked_site_is_paused_next_run(tmp_path, monkeypatch):
    import skycheck.main as m
    from skycheck.providers.base import Provider, ProviderBlocked

    calls = []

    class Blocky(Provider):
        name = "skyscanner"

        def search(self, trip):
            calls.append(trip)
            raise ProviderBlocked("captcha")

    cfg = {**CFG, "database": str(tmp_path / "db.sqlite"), "report_file": str(tmp_path / "r.md")}
    monkeypatch.setattr(m, "build_providers", lambda c: [Blocky(c)])
    m.run(cfg, send=False)
    m.run(cfg, send=False)
    assert len(calls) == 1  # la segunda vez ni lo intenta
    assert "en pausa" in (tmp_path / "r.md").read_text()


def test_only_and_skip(tmp_path, monkeypatch):
    import skycheck.main as m
    from skycheck.providers.base import Provider

    ran = []

    def mk(n):
        class P(Provider):
            name = n

            def search(self, trip):
                ran.append(self.name)
                return []
        return P

    cfg = {**CFG, "database": str(tmp_path / "db.sqlite"), "report_file": str(tmp_path / "r.md")}
    monkeypatch.setattr(m, "build_providers", lambda c: [mk("google_flights")(c), mk("despegar")(c)])
    m.run(cfg, send=False, only=["google_flights"])
    assert set(ran) == {"google_flights"}
    ran.clear()
    m.run(cfg, send=False, skip=["google_flights"])
    assert set(ran) == {"despegar"}


def test_waits_for_human_to_solve_captcha(monkeypatch):
    monkeypatch.setenv("SKYCHECK_HEADLESS", "false")
    cfg = {**CFG, "browser": {"headless": False, "wait_for_captcha_minutes": 1}}
    sp = ScraperProvider("skyscanner", cfg)

    class FakePage:
        def __init__(self):
            self.n = 0

        def wait_for_timeout(self, ms):
            self.n += 1

        def inner_text(self, sel):
            return "Are you a robot?" if self.n < 3 else "Resultados US$ 700"

    page = FakePage()
    assert sp._is_blocked(page)
    assert sp._wait_for_human(page) is True

    monkeypatch.setenv("SKYCHECK_HEADLESS", "true")
    assert sp._wait_for_human(FakePage()) is False  # en servidor no espera
