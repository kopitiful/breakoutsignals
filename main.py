"""
One-shot CLI runner — runs the full pipeline for all 4 markets.
Usage:
  python main.py                  # Europa + Nasdaq + S&P 500 + Russell
  python main.py AAPL MSFT TSLA  # specific tickers (custom table)
"""

import logging
import sys

from config.settings import (
    TICKERS_EU_CSV, TICKERS_NASDAQ_CSV, TICKERS_SP500_CSV, TICKERS_RUSSELL_CSV
)
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


MARKETS = [
    (TICKERS_EU_CSV,      "europa",  "EUROPA"),
    (TICKERS_NASDAQ_CSV,  "nasdaq",  "NASDAQ 100"),
    (TICKERS_SP500_CSV,   "sp500",   "S&P 500"),
    (TICKERS_RUSSELL_CSV, "russell", "RUSSELL 2000"),
]

if __name__ == "__main__":
    explicit_tickers = sys.argv[1:] or None

    if explicit_tickers:
        candidates = run(tickers=explicit_tickers, label="custom")
        _print_table(candidates, "CUSTOM")
    else:
        for csv_path, label, title in MARKETS:
            candidates = run(tickers=load_tickers(csv_path), label=label)
            _print_table(candidates, title)
