"""
Main analysis pipeline — runs for a single day's batch.

Order:
  1. Fetch / refresh market data
  2. Analyse each ticker in parallel (multiprocessing)
  3. Filter to actionable signals only (active patterns + recent breakouts)
  4. Persist signals + send alerts
"""

import logging
import multiprocessing as mp
from datetime import date, timedelta

import pandas as pd

from config.settings import (
    DETECTION_LOOKBACK_WEEKS,
    SIGNAL_MAX_STALENESS_WEEKS,
    SIGNAL_MAX_BREAKOUT_WEEKS,
    SIGNAL_PRICE_PROXIMITY_PCT,
)
from data.fetcher import fetch_all, load_tickers
from detection import rectangle, triangle, head_shoulders
from classification.breakout import classify
from signals.scorer import score
from signals.targets import calculate
from signals.writer import save_signals
from signals.charts import generate_all
from alerts.telegram import send_alerts
from detection.base import PatternCandidate

log = logging.getLogger(__name__)

DETECTORS  = [rectangle.detect, triangle.detect, head_shoulders.detect]
TABLE_ROWS = 20   # must match main.py display limit


def _is_actionable(c: PatternCandidate, last_close: float, last_bar_date: date) -> bool:
    """
    Return True only if this signal is tradeable NOW (upside only).

    Case A — Pending (no breakout yet):
      • Current price is still inside the pattern boundaries (consolidation ongoing)
      • Breakout could happen any day → always show these

    Case B — Recent breakout Type 1 or 2:
      • Breakout within SIGNAL_MAX_BREAKOUT_WEEKS (still enterable)
      • Price hasn't run more than 1.5× the measured move past entry

    Type 3, Type 4, old breakouts, downside signals → discard.
    """
    # Only upside signals: entry zone must be at/above the upper bound
    if c.entry_zone_low < c.upper_bound * 0.97:
        return False

    if c.breakout_type == "pending":
        # Price must be inside the pattern right now — this is the core check
        return c.lower_bound <= last_close <= c.upper_bound

    if c.breakout_type in ("type1", "type2"):
        if c.breakout_date is None:
            return False
        breakout_cutoff = last_bar_date - timedelta(weeks=SIGNAL_MAX_BREAKOUT_WEEKS)
        if c.breakout_date < breakout_cutoff:
            return False

        # Determine breakout direction from entry zone position
        up = c.entry_zone_low >= c.upper_bound * 0.97   # entry above resistance → upside break
        dn = c.entry_zone_high <= c.lower_bound * 1.03  # entry below support → downside break

        if up:
            # Price must be above pattern floor and within 8% below entry
            # (deeper than 8% below entry = breakout failed, not a retest)
            if last_close < c.lower_bound:
                return False
            if last_close < c.entry_zone_low * 0.92:
                return False
            # Max 8% above entry — beyond that the move is too far gone
            max_chase = c.entry_zone_high * 1.08
            return last_close <= max_chase
        if dn:
            # Price must be below pattern ceiling and within 8% above entry
            if last_close > c.upper_bound:
                return False
            if last_close > c.entry_zone_high * 1.08:
                return False
            min_chase = c.entry_zone_low * (1 - c.measured_move_pct / 100)
            return last_close >= min_chase

        return True   # direction ambiguous — keep and let trader decide

    return False


def _analyse_ticker(args: tuple[str, pd.DataFrame]) -> list[PatternCandidate]:
    """Worker function — runs in a subprocess."""
    ticker, df = args

    if len(df) > DETECTION_LOOKBACK_WEEKS:
        df = df.iloc[-DETECTION_LOOKBACK_WEEKS:]

    last_close    = float(df["close"].iloc[-1])
    last_bar_date = df.index[-1]

    candidates: list[PatternCandidate] = []
    for detect in DETECTORS:
        candidates.extend(detect(ticker, df))

    actionable = []
    filtered   = 0
    for c in candidates:
        classify(c, df)
        calculate(c)   # entry zone must be set before actionability check
        if _is_actionable(c, last_close, last_bar_date):
            score(c, df)
            c.last_close = last_close
            actionable.append(c)
        else:
            filtered += 1

    if filtered:
        log.debug("%s: %d stale/inactive patterns filtered out", ticker, filtered)

    return actionable


def run(tickers: list[str] | None = None, run_date: date | None = None,
        label: str = "US") -> list[PatternCandidate]:
    run_date = run_date or date.today()
    log.info("=== Aksel pipeline [%s] starting for %s ===", label, run_date)

    if tickers is None:
        tickers = load_tickers()

    data = fetch_all(tickers)
    items = [(t, df) for t, df in data.items() if not df.empty and len(df) >= 20]

    workers = max(1, mp.cpu_count() - 1)
    log.info("Analysing %d tickers on %d cores ...", len(items), workers)

    with mp.Pool(processes=workers) as pool:
        results = pool.map(_analyse_ticker, items)

    all_candidates: list[PatternCandidate] = [c for batch in results for c in batch]
    all_candidates.sort(key=lambda c: c.score, reverse=True)

    log.info(
        "Actionable signals: %d across %d tickers",
        len(all_candidates), len(items),
    )

    saved = save_signals(all_candidates, run_date)
    generate_all(all_candidates[:TABLE_ROWS], data)
    send_alerts(all_candidates)

    log.info("Pipeline complete: %d signals saved.", saved)
    return all_candidates
