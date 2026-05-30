"""Shared utilities for all pattern detectors."""

from dataclasses import dataclass, field
from datetime import date


@dataclass
class PatternCandidate:
    ticker: str
    pattern_type: str
    pattern_start_date: date
    pattern_end_date: date
    pattern_duration_weeks: int
    upper_bound: float
    lower_bound: float
    touches_upper: int = 0
    touches_lower: int = 0
    # populated by breakout classifier
    breakout_type: str = "pending"
    breakout_date: date | None = None
    # "full" | "volume" | "time" | "none" | "pending"
    confirmed: str = "pending"
    # populated by scorer
    score: float = 0.0
    # set by pipeline — last available weekly close
    last_close: float = 0.0
    # set by writer — date this signal was first seen in the DB
    first_seen_days: int = 0
    # populated by signal writer
    entry_zone_low: float = 0.0
    entry_zone_high: float = 0.0
    stop_loss: float = 0.0
    price_target: float = 0.0
    measured_move_pct: float = 0.0
    status: str = "active"
    # raw bars kept for downstream processing
    meta: dict = field(default_factory=dict)


def find_swing_highs(highs, order: int = 3) -> list[int]:
    """Return indices of local maxima with given order (bars on each side)."""
    peaks = []
    n = len(highs)
    for i in range(order, n - order):
        window = highs[i - order: i + order + 1]
        if highs[i] == max(window):
            peaks.append(i)
    return peaks


def find_swing_lows(lows, order: int = 3) -> list[int]:
    """Return indices of local minima with given order (bars on each side)."""
    troughs = []
    n = len(lows)
    for i in range(order, n - order):
        window = lows[i - order: i + order + 1]
        if lows[i] == min(window):
            troughs.append(i)
    return troughs
