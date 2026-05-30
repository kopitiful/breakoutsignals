"""
Head & Shoulders (H&S) and Inverse H&S (IH&S) detector.

H&S  — bearish reversal: three swing highs, middle (head) is highest,
        shoulders roughly equal height, neckline through the two troughs.

IH&S — bullish reversal: three swing lows, middle (head) is lowest,
        shoulders roughly equal depth, neckline through the two peaks.

Pattern layout (H&S):

        Head
        /\
   LS  /  \  RS
  /\  /    \  /\
 /  \/      \/  \
     NL----NL
          ↑ neckline

Algorithm per pattern type:
  1. Collect all swing extremes (highs for H&S, lows for IH&S).
  2. For every triplet (i, j, k) of consecutive swing extremes:
     a. Middle extreme must be more extreme than both sides
        (head > both shoulders for H&S; head < both shoulders for IH&S).
     b. Left and right shoulder must be within HS_SHOULDER_TOLERANCE of each other.
     c. Locate the two reaction points between ls–head and head–rs
        (lows for H&S, highs for IH&S) — these define the neckline.
     d. Minimum duration: HS_MIN_WEEKS total span.
  3. upper_bound / lower_bound = neckline value at pattern end (used by
     breakout classifier and target calculator).
"""

import logging

import numpy as np
import pandas as pd
from scipy import stats

from config.settings import HS_SHOULDER_TOLERANCE, RECTANGLE_MIN_WEEKS as HS_MIN_WEEKS
from detection.base import PatternCandidate, find_swing_highs, find_swing_lows

log = logging.getLogger(__name__)


def detect(ticker: str, df: pd.DataFrame) -> list[PatternCandidate]:
    if len(df) < HS_MIN_WEEKS + 6:
        return []

    highs  = df["high"].values
    lows   = df["low"].values
    dates  = list(df.index)

    candidates: list[PatternCandidate] = []
    candidates += _detect_hs(ticker, highs, lows, dates)
    candidates += _detect_ihs(ticker, highs, lows, dates)

    log.debug("%s: %d H&S candidates", ticker, len(candidates))
    return candidates


# ── H&S (bearish) ──────────────────────────────────────────────────────────

def _detect_hs(ticker, highs, lows, dates) -> list[PatternCandidate]:
    sh_idx = find_swing_highs(highs, order=3)
    results = []

    for a, b, c in _triplets(sh_idx):
        ls_h = highs[a]   # left shoulder high
        hd_h = highs[b]   # head high
        rs_h = highs[c]   # right shoulder high

        # Head must be highest
        if not (hd_h > ls_h and hd_h > rs_h):
            continue

        # Shoulders within tolerance
        if abs(ls_h - rs_h) / ls_h > HS_SHOULDER_TOLERANCE:
            continue

        # Duration check
        duration = c - a + 1
        if duration < HS_MIN_WEEKS:
            continue

        # Neckline: two reaction lows — one between a..b, one between b..c
        nl_left_idx  = _trough_between(lows, a, b)
        nl_right_idx = _trough_between(lows, b, c)
        if nl_left_idx is None or nl_right_idx is None:
            continue

        nl_left_val  = lows[nl_left_idx]
        nl_right_val = lows[nl_right_idx]

        # Neckline as linear regression through the two points
        neckline_at_end = _neckline_value(
            nl_left_idx, nl_left_val,
            nl_right_idx, nl_right_val,
            at=c,
        )

        # Pattern height = head to neckline (used for measured move)
        height = hd_h - neckline_at_end
        if height <= 0:
            continue

        results.append(PatternCandidate(
            ticker=ticker,
            pattern_type="hs",
            pattern_start_date=dates[a],
            pattern_end_date=dates[c],
            pattern_duration_weeks=duration,
            # Breakout classifier: bearish break = close < lower_bound
            # → lower_bound = neckline, upper_bound = head (pattern ceiling)
            upper_bound=hd_h,
            lower_bound=neckline_at_end,
            touches_upper=1,   # head
            touches_lower=2,   # two neckline touches
            meta={
                "head_high":        hd_h,
                "ls_high":          ls_h,
                "rs_high":          rs_h,
                "nl_left":          nl_left_val,
                "nl_right":         nl_right_val,
                "neckline_at_end":  neckline_at_end,
                "height":           height,
                "prior_trend":      "down",
            },
        ))

    return results


# ── IH&S (bullish) ─────────────────────────────────────────────────────────

def _detect_ihs(ticker, highs, lows, dates) -> list[PatternCandidate]:
    sl_idx = find_swing_lows(lows, order=3)
    results = []

    for a, b, c in _triplets(sl_idx):
        ls_l = lows[a]   # left shoulder low
        hd_l = lows[b]   # head low
        rs_l = lows[c]   # right shoulder low

        # Head must be lowest
        if not (hd_l < ls_l and hd_l < rs_l):
            continue

        # Shoulders within tolerance
        if abs(ls_l - rs_l) / ls_l > HS_SHOULDER_TOLERANCE:
            continue

        # Duration check
        duration = c - a + 1
        if duration < HS_MIN_WEEKS:
            continue

        # Neckline: two reaction highs
        nl_left_idx  = _peak_between(highs, a, b)
        nl_right_idx = _peak_between(highs, b, c)
        if nl_left_idx is None or nl_right_idx is None:
            continue

        nl_left_val  = highs[nl_left_idx]
        nl_right_val = highs[nl_right_idx]

        neckline_at_end = _neckline_value(
            nl_left_idx, nl_left_val,
            nl_right_idx, nl_right_val,
            at=c,
        )

        height = neckline_at_end - hd_l
        if height <= 0:
            continue

        results.append(PatternCandidate(
            ticker=ticker,
            pattern_type="ihs",
            pattern_start_date=dates[a],
            pattern_end_date=dates[c],
            pattern_duration_weeks=duration,
            # Breakout classifier: bullish break = close > upper_bound
            # → upper_bound = neckline, lower_bound = head (pattern floor)
            upper_bound=neckline_at_end,
            lower_bound=hd_l,
            touches_upper=2,   # two neckline touches
            touches_lower=1,   # head
            meta={
                "head_low":         hd_l,
                "ls_low":           ls_l,
                "rs_low":           rs_l,
                "nl_left":          nl_left_val,
                "nl_right":         nl_right_val,
                "neckline_at_end":  neckline_at_end,
                "height":           height,
                "prior_trend":      "up",
            },
        ))

    return results


# ── Helpers ────────────────────────────────────────────────────────────────

def _triplets(indices: list[int]):
    """Yield every consecutive triplet (i, j, k) from a sorted index list."""
    for i in range(len(indices) - 2):
        yield indices[i], indices[i + 1], indices[i + 2]


def _trough_between(lows, start: int, end: int) -> int | None:
    """Index of the lowest bar strictly between start and end."""
    segment = lows[start + 1: end]
    if len(segment) == 0:
        return None
    return start + 1 + int(np.argmin(segment))


def _peak_between(highs, start: int, end: int) -> int | None:
    """Index of the highest bar strictly between start and end."""
    segment = highs[start + 1: end]
    if len(segment) == 0:
        return None
    return start + 1 + int(np.argmax(segment))


def _neckline_value(idx1: int, val1: float, idx2: int, val2: float, at: int) -> float:
    """Interpolate / extrapolate neckline to bar index `at`."""
    if idx2 == idx1:
        return val1
    slope = (val2 - val1) / (idx2 - idx1)
    return val1 + slope * (at - idx1)
