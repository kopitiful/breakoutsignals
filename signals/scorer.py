"""
Signal scorer: 0–100 composite score.

  40% — pattern quality (touches, duration)
  30% — volume at breakout vs 20-week average
  20% — breakout type  (Type1=1.0, Type2=0.75, pending=0.5, Type3/4=0.0)
  10% — historical success rate (Kibar baseline)

Final score is then multiplied by a confirmation factor:
  full    → ×1.25   (both volume AND 2 consecutive closes confirmed)
  volume  → ×1.10   (volume confirmed only)
  time    → ×1.10   (consecutive closes confirmed only)
  none    → ×0.75   (unconfirmed breakout — treat with caution)
  pending → ×1.00   (no breakout yet — no penalty/bonus)
"""

import numpy as np
import pandas as pd

from config.settings import (
    SCORE_PATTERN_QUALITY, SCORE_VOLUME_BREAKOUT,
    SCORE_BREAKOUT_TYPE, SCORE_HISTORICAL_RATE,
    VOLUME_LOOKBACK_WEEKS,
)
from detection.base import PatternCandidate

_BREAKOUT_TYPE_WEIGHT = {
    "type1":   1.00,
    "type2":   0.75,
    "type3":   0.00,
    "type4":   0.00,
    "pending": 0.50,
}

_CONFIRMATION_FACTOR = {
    "full":    1.25,
    "volume":  1.10,
    "time":    1.10,
    "none":    0.75,
    "pending": 1.00,
}

_HISTORICAL_RATE = {
    "rectangle":     0.72,
    "triangle_sym":  0.65,
    "triangle_asc":  0.68,
    "triangle_desc": 0.66,
    "hs":            0.63,
    "ihs":           0.67,
}


def _quality_score(c: PatternCandidate) -> float:
    touch_score    = min((c.touches_upper + c.touches_lower) / 8.0, 1.0)
    duration_score = min(c.pattern_duration_weeks / 26.0, 1.0)
    return 0.6 * touch_score + 0.4 * duration_score


def _volume_score(c: PatternCandidate, df: pd.DataFrame) -> float:
    if c.breakout_date is None or c.breakout_type == "pending":
        return 0.5

    dates = list(df.index)
    try:
        bk_pos = dates.index(c.breakout_date)
    except ValueError:
        return 0.5

    bk_vol  = df["volume"].iloc[bk_pos]
    avg_vol = df["volume"].iloc[max(0, bk_pos - VOLUME_LOOKBACK_WEEKS): bk_pos].mean()

    if avg_vol == 0 or np.isnan(avg_vol):
        return 0.5

    return min(bk_vol / avg_vol / 3.0, 1.0)   # 3× avg = full score


def score(c: PatternCandidate, df: pd.DataFrame) -> float:
    q  = _quality_score(c)
    v  = _volume_score(c, df)
    bt = _BREAKOUT_TYPE_WEIGHT.get(c.breakout_type, 0.0)
    hr = _HISTORICAL_RATE.get(c.pattern_type, 0.65)

    raw = (
        SCORE_PATTERN_QUALITY * q  +
        SCORE_VOLUME_BREAKOUT  * v  +
        SCORE_BREAKOUT_TYPE    * bt +
        SCORE_HISTORICAL_RATE  * hr
    )

    factor = _CONFIRMATION_FACTOR.get(c.confirmed, 1.0)
    c.score = round(min(raw * factor * 100, 100.0), 1)
    return c.score
