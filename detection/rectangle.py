"""
Rectangle pattern detector.

Algorithm:
  1. Find all swing highs and swing lows on the weekly series.
  2. Slide a window over consecutive swing pairs and test whether the
     highs cluster within RECTANGLE_TOLERANCE of a horizontal resistance
     and the lows cluster within tolerance of a horizontal support.
  3. Require MIN_TOUCHES on each side and MIN_WEEKS duration.
  4. Yield a PatternCandidate for each qualifying window.
"""

import logging

import numpy as np
import pandas as pd

from config.settings import (
    RECTANGLE_TOLERANCE, RECTANGLE_MIN_WEEKS, RECTANGLE_MIN_TOUCHES
)
from detection.base import PatternCandidate, find_swing_highs, find_swing_lows

log = logging.getLogger(__name__)


def _touches_in_band(values: np.ndarray, level: float, tol: float) -> int:
    return int(np.sum(np.abs(values - level) / level <= tol))


def detect(ticker: str, df: pd.DataFrame) -> list[PatternCandidate]:
    if len(df) < RECTANGLE_MIN_WEEKS + 6:
        return []

    highs  = df["high"].values
    lows   = df["low"].values
    dates  = list(df.index)

    swing_high_idx = find_swing_highs(highs)
    swing_low_idx  = find_swing_lows(lows)

    candidates: list[PatternCandidate] = []

    # Slide window: try every pair of swing-high start / end
    for i, sh_start in enumerate(swing_high_idx):
        for sh_end in swing_high_idx[i + 1:]:
            # Duration check
            duration = sh_end - sh_start + 1
            if duration < RECTANGLE_MIN_WEEKS:
                continue

            # Candidate resistance: median of swing highs in window
            window_sh = [idx for idx in swing_high_idx if sh_start <= idx <= sh_end]
            if len(window_sh) < RECTANGLE_MIN_TOUCHES:
                continue
            resistance = float(np.median(highs[window_sh]))

            # All swing highs must be within tolerance of resistance
            if not all(
                abs(highs[idx] - resistance) / resistance <= RECTANGLE_TOLERANCE
                for idx in window_sh
            ):
                continue

            # Swing lows in the same window
            window_sl = [idx for idx in swing_low_idx if sh_start <= idx <= sh_end]
            if len(window_sl) < RECTANGLE_MIN_TOUCHES:
                continue
            support = float(np.median(lows[window_sl]))

            if not all(
                abs(lows[idx] - support) / support <= RECTANGLE_TOLERANCE
                for idx in window_sl
            ):
                continue

            # Sanity: meaningful height (at least 3% range)
            height_pct = (resistance - support) / support
            if height_pct < 0.03:
                continue

            c = PatternCandidate(
                ticker=ticker,
                pattern_type="rectangle",
                pattern_start_date=dates[sh_start],
                pattern_end_date=dates[sh_end],
                pattern_duration_weeks=duration,
                upper_bound=resistance,
                lower_bound=support,
                touches_upper=len(window_sh),
                touches_lower=len(window_sl),
                meta={
                    "height_pct": height_pct,
                    "swing_high_indices": window_sh,
                    "swing_low_indices": window_sl,
                },
            )
            candidates.append(c)

    # De-duplicate overlapping rectangles: keep the one with most touches
    candidates = _dedup(candidates)

    log.debug("%s: %d rectangle candidates", ticker, len(candidates))
    return candidates


def _dedup(candidates: list[PatternCandidate]) -> list[PatternCandidate]:
    """Remove rectangles whose date ranges are fully contained in a better one."""
    if len(candidates) <= 1:
        return candidates

    candidates.sort(key=lambda c: c.touches_upper + c.touches_lower, reverse=True)
    kept = []
    for c in candidates:
        overlap = False
        for k in kept:
            if c.pattern_start_date >= k.pattern_start_date and c.pattern_end_date <= k.pattern_end_date:
                overlap = True
                break
        if not overlap:
            kept.append(c)
    return kept
