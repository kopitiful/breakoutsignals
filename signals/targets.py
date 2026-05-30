"""
Entry zone, stop-loss and price target (Kibar measured move).

For rectangles / triangles:
  height = upper_bound - lower_bound
  direction determines which side breaks

For H&S / IH&S:
  The neckline is the breakout level (stored in meta['neckline_at_end']).
  height = meta['height'] (head-to-neckline distance).
  entry is at / just below the neckline (H&S) or above it (IH&S).
"""

from detection.base import PatternCandidate


def calculate(c: PatternCandidate) -> PatternCandidate:
    direction = _infer_direction(c)

    if c.pattern_type in ("hs", "ihs"):
        neckline = c.meta["neckline_at_end"]
        height   = c.meta["height"]
        height_pct = height / neckline

        if direction == "down":   # H&S bearish
            c.entry_zone_low  = neckline * 0.995
            c.entry_zone_high = neckline
            c.stop_loss       = neckline * 1.02       # 2% above neckline
            c.price_target    = neckline - height
        else:                     # IH&S bullish
            c.entry_zone_low  = neckline
            c.entry_zone_high = neckline * 1.005
            c.stop_loss       = neckline * 0.98       # 2% below neckline
            c.price_target    = neckline + height
    else:
        height     = c.upper_bound - c.lower_bound
        height_pct = height / c.lower_bound

        if direction == "up":
            c.entry_zone_low  = c.upper_bound
            c.entry_zone_high = c.upper_bound * 1.005
            c.stop_loss       = c.upper_bound * 0.98
            c.price_target    = c.upper_bound + height
        else:
            c.entry_zone_low  = c.lower_bound * 0.995
            c.entry_zone_high = c.lower_bound
            c.stop_loss       = c.lower_bound * 1.02
            c.price_target    = c.lower_bound - height

    c.measured_move_pct = round(height_pct * 100, 2)
    return c


def _infer_direction(c: PatternCandidate) -> str:
    # Use actual breakout direction when the classifier has determined it
    if c.breakout_type not in ("pending",) and "breakout_direction" in c.meta:
        return c.meta["breakout_direction"]
    # For pending patterns fall back to expected direction
    if c.pattern_type in ("rectangle", "triangle_sym"):
        return c.meta.get("prior_trend", "up")
    if c.pattern_type in ("triangle_asc", "ihs"):
        return "up"
    if c.pattern_type in ("triangle_desc", "hs"):
        return "down"
    return "up"
