"""
Triangle pattern detector (symmetrical, ascending, descending).

Iterates over pairs of swing-high indices as window boundaries instead of
every bar combination — reduces complexity from O(n²) to O(k²) where k
is the number of swing points (~n/7), giving a ~50× speedup.
"""

import logging

import numpy as np
import pandas as pd
from scipy import stats

from config.settings import TRIANGLE_MIN_WEEKS, TRIANGLE_MAX_WEEKS, TRIANGLE_CONVERGENCE_R2
from detection.base import PatternCandidate, find_swing_highs, find_swing_lows

log = logging.getLogger(__name__)

_FLAT_SLOPE_THRESHOLD = 0.0003


def _linreg(indices: np.ndarray, values: np.ndarray):
    slope, intercept, r, _, _ = stats.linregress(indices, values)
    return slope, intercept, r ** 2


def _norm_slope(slope: float, intercept: float, n_bars: int) -> float:
    mid_price = intercept + slope * (n_bars / 2)
    return slope / mid_price if mid_price else 0.0


def detect(ticker: str, df: pd.DataFrame) -> list[PatternCandidate]:
    if len(df) < TRIANGLE_MIN_WEEKS + 6:
        return []

    highs  = df["high"].values
    lows   = df["low"].values
    dates  = list(df.index)
    n      = len(df)

    sh_idx = np.array(find_swing_highs(highs))
    sl_idx = np.array(find_swing_lows(lows))

    if len(sh_idx) < 2 or len(sl_idx) < 2:
        return []

    candidates: list[PatternCandidate] = []

    # Use swing-high start/end pairs as window boundaries — O(k²) not O(n²)
    for i in range(len(sh_idx)):
        for j in range(i + 1, len(sh_idx)):
            start = int(sh_idx[i])
            end   = int(sh_idx[j])
            duration = end - start + 1

            if duration < TRIANGLE_MIN_WEEKS:
                continue
            if duration > TRIANGLE_MAX_WEEKS:
                break   # further j only get longer — skip rest of inner loop

            win_sh = sh_idx[(sh_idx >= start) & (sh_idx <= end)]
            win_sl = sl_idx[(sl_idx >= start) & (sl_idx <= end)]

            if len(win_sh) < 2 or len(win_sl) < 2:
                continue

            sh_slope, sh_int, sh_r2 = _linreg(win_sh, highs[win_sh])
            sl_slope, sl_int, sl_r2 = _linreg(win_sl, lows[win_sl])

            if sh_r2 < TRIANGLE_CONVERGENCE_R2 or sl_r2 < TRIANGLE_CONVERGENCE_R2:
                continue

            sh_norm = _norm_slope(sh_slope, sh_int, n)
            sl_norm = _norm_slope(sl_slope, sl_int, n)

            sh_flat = abs(sh_norm) < _FLAT_SLOPE_THRESHOLD
            sl_flat = abs(sl_norm) < _FLAT_SLOPE_THRESHOLD

            if sh_norm < -_FLAT_SLOPE_THRESHOLD and sl_norm > _FLAT_SLOPE_THRESHOLD:
                ptype = "triangle_sym"
            elif sl_norm > _FLAT_SLOPE_THRESHOLD and sh_flat:
                ptype = "triangle_asc"
            elif sh_norm < -_FLAT_SLOPE_THRESHOLD and sl_flat:
                ptype = "triangle_desc"
            else:
                continue

            upper = sh_int + sh_slope * end
            lower = sl_int + sl_slope * end

            if upper <= lower:
                continue

            candidates.append(PatternCandidate(
                ticker=ticker,
                pattern_type=ptype,
                pattern_start_date=dates[start],
                pattern_end_date=dates[end],
                pattern_duration_weeks=duration,
                upper_bound=upper,
                lower_bound=lower,
                touches_upper=int(len(win_sh)),
                touches_lower=int(len(win_sl)),
                meta={"sh_slope": sh_slope, "sh_r2": sh_r2,
                      "sl_slope": sl_slope, "sl_r2": sl_r2},
            ))

    candidates = _dedup(candidates)
    log.debug("%s: %d triangle candidates", ticker, len(candidates))
    return candidates


def _dedup(candidates: list[PatternCandidate]) -> list[PatternCandidate]:
    if len(candidates) <= 1:
        return candidates
    candidates.sort(key=lambda c: c.pattern_duration_weeks, reverse=True)
    kept = []
    for c in candidates:
        overlap = any(
            c.pattern_start_date >= k.pattern_start_date
            and c.pattern_end_date <= k.pattern_end_date
            and c.pattern_type == k.pattern_type
            for k in kept
        )
        if not overlap:
            kept.append(c)
    return kept
