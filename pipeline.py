"""
Main analysis pipeline — runs for a single day's batch.
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
TABLE_ROWS = 20


def _is_actionable(c: PatternCandidate, last_close: float, last_bar_date: date) -> bool:
    if c.entry_zone_low < c.upper_bound * 0.97:
        return False

    if c.breakout_type == "pending":
        return c.lower_bound <= last_close <= c.upper_bound

    if c.breakout_type in ("type1", "type2"):
        if c.breakout_date is None:
            return False
        breakout_cutoff = last_bar_date - timedelta(weeks=SIGNAL_MAX_BREAKOUT_WEEKS)
        if c.breakout_date < breakout_cutoff:
            return False

        up = c.entry_zone_low >= c.upper_bound * 0.97
        dn = c.entry_zone_high <= c.lower_bound * 1.03

        if up:
            if last_close < c.lower_bound:
                return False
            if last_close < c.entry_zone_low * 0.92:
                return False
            max_chase = c.entry_zone_high * 1.08
            return last_close <= max_chase
        if dn:
            if last_close > c.upper_bound:
                return False
            if last_close > c.entry_zone_high * 1.08:
                return False
            min_chase = c.entry_zone_low * (1 - c.measured_move_pct / 100)
            return last_close >= min_chase

        return True

    return False


def _analyse_ticker(args: tuple[str, pd.DataFrame]) -> list[PatternCandidate]:
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
        calculate(c)
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
        label: str = "us") -> list[PatternCandidate]:
    run_date = run_date or date.today()
    log.info("=== Pipeline [%s] starting for %s ===", label, run_date)

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

    log.info("Actionable signals: %d across %d tickers", len(all_candidates), len(items))

    saved = save_signals(all_candidates, run_date, market=label.lower())
    generate_all(all_candidates, data)
    send_alerts(all_candidates)

    log.info("Pipeline complete: %d signals saved.", saved)
    return all_candidates
