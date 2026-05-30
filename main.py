"""
One-shot CLI runner — runs the full pipeline for US and European markets.
Usage:
  python main.py                  # US + EU tickers from config/
  python main.py AAPL MSFT TSLA  # specific tickers (US table only)
"""

import logging
import sys

from config.settings import TICKERS_EU_CSV
from data.fetcher import load_tickers
from pipeline import run, TABLE_ROWS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)

HEADER = (f"\n{'TICKER':<10} {'PATTERN':<16} {'BK TYPE':<10} {'CONFIRM':<8} "
          f"{'SCORE':>5}  {'LAST':>9} {'ENTRY LOW':>10} {'TARGET':>10}  {'MOVE%':>6}  {'DIST':>7}  {'DAYS':>4}")
DIVIDER = "-" * 117


def _dist_label(c) -> str:
    """Distance of last_close from entry_zone_low as a signed percentage."""
    if c.entry_zone_low <= 0:
        return "     —"
    pct = (c.last_close - c.entry_zone_low) / c.entry_zone_low * 100
    if abs(pct) < 0.5:
        return "  entry"
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:>5.1f}%"


def _print_table(candidates, title: str) -> None:
    print(f"\n{'═' * 117}")
    print(f"  {title}")
    print('═' * 117)
    print(HEADER)
    print(DIVIDER)
    for c in candidates[:TABLE_ROWS]:
        days = f"{c.first_seen_days:>4}d" if c.first_seen_days > 0 else "  neu"
        print(
            f"{c.ticker:<10} {c.pattern_type:<16} {c.breakout_type:<10} {c.confirmed:<8} "
            f"{c.score:>5.1f}  {c.last_close:>9.2f} {c.entry_zone_low:>10.2f} {c.price_target:>10.2f}  "
            f"{c.measured_move_pct:>6.1f}%  {_dist_label(c):>7}  {days}"
        )
    if not candidates:
        print("  (keine aktiven Signale)")


if __name__ == "__main__":
    explicit_tickers = sys.argv[1:] or None

    if explicit_tickers:
        candidates = run(tickers=explicit_tickers, label="CUSTOM")
        _print_table(candidates, "CUSTOM")
    else:
        us_candidates = run(tickers=load_tickers(), label="US")
        eu_candidates = run(tickers=load_tickers(TICKERS_EU_CSV), label="EU")

        _print_table(us_candidates,  "US MARKETS  (Long-Signale, nach Score sortiert)")
        _print_table(eu_candidates,  "EU MARKETS  (Long-Signale, nach Score sortiert)")

    print("""
LEGENDE  (nur Long-Signale / Ausbrüche nach oben)
───────────────────────────────────────────────────────────────────────────────
TICKER    Symbol  (EU-Ticker mit Börsen-Suffix, z.B. SAP.DE, ASML.AS, NOVO-B.CO)
PATTERN   rectangle       Rechteck-Konsolidierung (horizontale Bänder)
          triangle_sym    Symmetrisches Dreieck (Ausbruch nach oben)
          triangle_asc    Aufsteigendes Dreieck (flache Highs + steigende Lows)
          ihs             Inv. Head & Shoulders — bullisch, Ausbruch nach oben

BK TYPE   pending         Noch kein Ausbruch — Kurs still im Muster (Watchlist!)
          type1           Sauberer Ausbruch, Kurs bleibt außerhalb
          type2           Ausbruch mit Retest an der Grenze (Wick), kein Close darunter

CONFIRM   full            Volumen ≥1,5× Ø UND 2 Closes außerhalb → höchste Qualität
          volume          Nur Volumen bestätigt
          time            Nur 2 aufeinanderfolgende Closes außerhalb bestätigt
          none            Ausbruch ohne Bestätigung — Vorsicht
          pending         Noch kein Ausbruch, keine Bestätigung möglich

SCORE     0–100  Composite-Score: Qualität (40%) + Volumen (30%) + BK-Typ (20%)
                 + hist. Erfolgsrate (10%), multipliziert mit Confirmations-Faktor
                 full=×1.25  volume/time=×1.10  none=×0.75

ENTRY LOW Untere Kante der Einstiegszone (knapp über Ausbruchsgrenze)
TARGET    Kursziel (gemessener Move = Musterhöhe ab Ausbruchspunkt projiziert)
MOVE%     Erwartete Bewegung in % von Entry bis Target
DIST      Abstand des aktuellen Kurses zur Entry-Zone
          "entry"   Kurs liegt praktisch auf der Einstiegslinie (±0,5%)
          negativ   Kurs noch unterhalb Entry → Ausbruch noch nicht erreicht
          positiv   Kurs bereits über Entry → je größer, desto mehr nachlaufen
DAYS      Tage seit diesem Signal zum ersten Mal in der Tabelle erschienen ist
          "neu"     Signal wird heute zum ersten Mal gesehen
───────────────────────────────────────────────────────────────────────────────
Charts:  signals/output/charts/   CSV: signals/output/signals_DATUM.csv
""")
