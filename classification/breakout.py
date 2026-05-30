"""
Breakout classifier — Kibar Type 1–4 taxonomy + two-layer confirmation.

Breakout types
  Type 1 — Clean: close outside boundary, stays there
  Type 2 — Retest: intraday wick back inside, but no close below boundary
  Type 3 — Shakeout: close re-enters pattern (stops hit), then resumes
  Type 4 — Failed: price crosses opposite boundary (pattern invalidated)

Confirmation layers (set on candidate.confirmed)
  volume  — breakout bar volume ≥ BREAKOUT_VOLUME_FACTOR × 20w average
  time    — BREAKOUT_CONFIRM_CLOSES consecutive closes outside boundary
  full    — both volume AND time confirmed
  none    — neither criterion met (treat signal with lower confidence)
  pending — no breakout yet
"""

import logging

import numpy as np
import pandas as pd

from config.settings import (
    BREAKOUT_VOLUME_FACTOR, BREAKOUT_CONFIRM_CLOSES, VOLUME_LOOKBACK_WEEKS
)
from detection.base import PatternCandidate

log = logging.getLogger(__name__)

REENTRY_TOLERANCE = 0.005


def classify(candidate: PatternCandidate, df: pd.DataFrame) -> PatternCandidate:
    dates = list(df.index)

    try:
        end_pos = dates.index(candidate.pattern_end_date)
    except ValueError:
        end_pos = next(
            (i for i, d in enumerate(dates) if d >= candidate.pattern_end_date),
            len(dates) - 1,
        )

    post = df.iloc[end_pos + 1:]

    if post.empty:
        candidate.breakout_type = "pending"
        candidate.confirmed     = "pending"
        return candidate

    resistance = candidate.upper_bound
    support    = candidate.lower_bound
    closes     = post["close"].values
    highs      = post["high"].values
    lows       = post["low"].values
    volumes    = post["volume"].values
    bar_dates  = list(post.index)

    # ── Find first breakout bar ───────────────────────────────────────────────

    breakout_bar = None
    direction    = None
    for i, close in enumerate(closes):
        if close > resistance:
            breakout_bar, direction = i, "up"
            break
        if close < support:
            breakout_bar, direction = i, "down"
            break

    if breakout_bar is None:
        candidate.breakout_type = "pending"
        candidate.confirmed     = "pending"
        return candidate

    candidate.breakout_date = bar_dates[breakout_bar]
    candidate.meta["breakout_direction"] = direction
    boundary  = resistance if direction == "up" else support
    sub_c     = closes[breakout_bar + 1:]
    sub_lo    = lows[breakout_bar + 1:]
    sub_hi    = highs[breakout_bar + 1:]
    opposite  = support if direction == "up" else resistance

    # ── Breakout type ─────────────────────────────────────────────────────────

    for close in sub_c:
        if (direction == "up"   and close < opposite) or \
           (direction == "down" and close > opposite):
            candidate.breakout_type = "type4"
            candidate.confirmed     = "none"
            return candidate

    for close in sub_c:
        if (direction == "up"   and close < boundary * (1 - REENTRY_TOLERANCE)) or \
           (direction == "down" and close > boundary * (1 + REENTRY_TOLERANCE)):
            candidate.breakout_type = "type3"
            candidate.confirmed     = "none"
            return candidate

    for lo, hi in zip(sub_lo, sub_hi):
        if direction == "up"   and lo < boundary * (1 - REENTRY_TOLERANCE):
            candidate.breakout_type = "type2"
            break
        if direction == "down" and hi > boundary * (1 + REENTRY_TOLERANCE):
            candidate.breakout_type = "type2"
            break
    else:
        candidate.breakout_type = "type1"

    # ── Confirmation ──────────────────────────────────────────────────────────

    # 1. Volume: breakout bar vs prior 20-week average
    bk_abs   = end_pos + 1 + breakout_bar
    avg_start = max(0, bk_abs - VOLUME_LOOKBACK_WEEKS)
    avg_vol   = df["volume"].iloc[avg_start:bk_abs].mean()
    bk_vol    = volumes[breakout_bar]
    vol_ok    = (
        not np.isnan(avg_vol)
        and avg_vol > 0
        and bk_vol >= BREAKOUT_VOLUME_FACTOR * avg_vol
    )

    # 2. Time: count consecutive closes outside boundary from breakout bar onward
    all_closes_from_bk = closes[breakout_bar:]
    consecutive = 0
    for close in all_closes_from_bk:
        outside = (direction == "up"   and close > boundary) or \
                  (direction == "down" and close < boundary)
        if outside:
            consecutive += 1
        else:
            consecutive = 0   # reset on any close back inside
    time_ok = consecutive >= BREAKOUT_CONFIRM_CLOSES

    if vol_ok and time_ok:
        candidate.confirmed = "full"
    elif vol_ok:
        candidate.confirmed = "volume"
    elif time_ok:
        candidate.confirmed = "time"
    else:
        candidate.confirmed = "none"

    return candidate
