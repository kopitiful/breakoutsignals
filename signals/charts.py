"""
Chart generator — one PNG per signal.

Layout:
  ┌───────────────────────────────────────────────┐
  │  AMZN · Rectangle · Type 1 Breakout · 64/100  │
  │  [Weekly candlesticks, 2 years]                │
  │  ─────── Resistance / upper_bound              │
  │  - - - - Support / lower_bound                 │
  │  ║ shaded pattern window                       │
  │  ▼ breakout bar                                │
  │  ──── Entry zone  ─·─ Stop  ····  Target       │
  ├───────────────────────────────────────────────┤
  │  [Volume bars, breakout bar highlighted]       │
  └───────────────────────────────────────────────┘

Saved to: signals/output/charts/TICKER_patterntype_YYYY-MM-DD.png
"""

import logging
from datetime import date, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")   # headless — no display needed
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd

from config.settings import SIGNALS_DIR
from detection.base import PatternCandidate

log = logging.getLogger(__name__)

CHARTS_DIR = SIGNALS_DIR / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# How many weeks before/after the pattern to show
PRE_PATTERN_WEEKS  = 30
POST_PATTERN_WEEKS = 36


def _prep_df(df: pd.DataFrame) -> pd.DataFrame:
    """Convert cache df (date index, lowercase cols) to mplfinance format."""
    out = df.copy()
    out.columns = [c.capitalize() for c in out.columns]
    out.index = pd.DatetimeIndex(out.index)
    return out.sort_index()


def _window(c: PatternCandidate, df: pd.DataFrame) -> pd.DataFrame:
    """Slice df to a display window around the pattern."""
    dates = list(df.index)
    try:
        start_pos = dates.index(c.pattern_start_date)
    except ValueError:
        start_pos = next((i for i, d in enumerate(dates) if d >= c.pattern_start_date), 0)

    end_pos = min(start_pos + c.pattern_duration_weeks + POST_PATTERN_WEEKS, len(dates) - 1)
    start_pos = max(0, start_pos - PRE_PATTERN_WEEKS)
    return df.iloc[start_pos: end_pos + 1]


def _pattern_hlines(c: PatternCandidate, win_df: pd.DataFrame):
    """
    Return upper and lower bound series aligned to the window index.
    For rectangles: horizontal lines.
    For triangles:  trendlines using stored slope/intercept from meta.
    For H&S/IH&S:  neckline.
    """
    idx = win_df.index
    n   = len(idx)

    if c.pattern_type in ("triangle_sym", "triangle_asc", "triangle_desc"):
        # Known: upper_bound / lower_bound are the trendline values AT pattern_end_date.
        # Known: sh_slope / sl_slope are in price-per-bar (weekly bar = 1 unit).
        # For any bar at offset k from pattern end:
        #   upper(k) = upper_bound + sh_slope * k
        #   lower(k) = lower_bound + sl_slope * k
        sh_slope = c.meta.get("sh_slope", 0.0)
        sl_slope = c.meta.get("sl_slope", 0.0)

        dates     = list(win_df.index)
        end_date  = pd.Timestamp(c.pattern_end_date).date()
        end_local = next(
            (i for i, d in enumerate(dates) if d >= end_date),
            n - 1,
        )

        # offset from pattern end: negative = before end, positive = after end
        offsets = np.arange(n) - end_local

        upper_vals = c.upper_bound + sh_slope * offsets
        lower_vals = c.lower_bound + sl_slope * offsets

        upper_series = pd.Series(np.maximum(upper_vals, 0.0), index=idx)
        lower_series = pd.Series(np.maximum(lower_vals, 0.0), index=idx)
    else:
        # Rectangle / H&S / IH&S — flat lines
        upper_series = pd.Series(c.upper_bound, index=idx)
        lower_series = pd.Series(c.lower_bound, index=idx)

    return upper_series, lower_series


def generate(c: PatternCandidate, df: pd.DataFrame) -> Path | None:
    """Generate and save a chart PNG for this signal. Returns the file path."""
    try:
        win = _window(c, df)
        if len(win) < 5:
            return None

        mpf_df = _prep_df(win)
        upper, lower = _pattern_hlines(c, win)

        # ── addplots ────────────────────────────────────────────────────────

        apds = [
            mpf.make_addplot(upper, panel=0, color="#e67e22",                             linestyle="--", secondary_y=False),
            mpf.make_addplot(lower, panel=0, color="#2980b9",                             linestyle="--", secondary_y=False),
        ]

        # Entry zone midline
        if c.entry_zone_low > 0:
            entry_mid = pd.Series((c.entry_zone_low + c.entry_zone_high) / 2, index=mpf_df.index)
            apds.append(mpf.make_addplot(entry_mid, panel=0, color="#27ae60",
                                         linestyle="-.", secondary_y=False))

        # Stop loss
        if c.stop_loss > 0:
            sl_series = pd.Series(c.stop_loss, index=mpf_df.index)
            apds.append(mpf.make_addplot(sl_series, panel=0, color="#e74c3c",
                                         linestyle=":", secondary_y=False))

        # Price target
        if c.price_target > 0 and c.price_target < mpf_df["High"].max() * 2:
            tgt_series = pd.Series(c.price_target, index=mpf_df.index)
            apds.append(mpf.make_addplot(tgt_series, panel=0, color="#8e44ad",
                                         linestyle=":", secondary_y=False))

        # ── mplfinance style ─────────────────────────────────────────────────

        mc = mpf.make_marketcolors(
            up="#26a69a", down="#ef5350",
            edge="inherit", wick="inherit",
            volume={"up": "#26a69a", "down": "#ef5350"},
        )
        style = mpf.make_mpf_style(
            marketcolors=mc, gridstyle="--", gridcolor="#2a2a2a",
            facecolor="#131722", figcolor="#131722",
            rc={"axes.labelcolor": "#d1d4dc", "xtick.color": "#d1d4dc",
                "ytick.color": "#d1d4dc", "text.color": "#d1d4dc"},
        )

        # ── plot ─────────────────────────────────────────────────────────────

        fig, axes = mpf.plot(
            mpf_df,
            type="candle",
            style=style,
            addplot=apds,
            volume=True,
            volume_panel=1,
            panel_ratios=(3, 1),
            figsize=(14, 7),
            returnfig=True,
            tight_layout=True,
        )

        ax = axes[0]

        # ── vertical padding ──────────────────────────────────────────────────
        y_low  = mpf_df["Low"].min()
        y_high = mpf_df["High"].max()
        ax.set_ylim(y_low * 0.75, y_high * 1.20)

        # ── shaded pattern window ─────────────────────────────────────────────

        dates_ts = list(mpf_df.index)
        try:
            p_start_ts = pd.Timestamp(c.pattern_start_date)
            p_end_ts   = pd.Timestamp(c.pattern_end_date)
            start_x = next((i for i, d in enumerate(dates_ts) if d >= p_start_ts), 0)
            end_x   = next((i for i, d in enumerate(dates_ts) if d >= p_end_ts), len(dates_ts) - 1)
            ax.axvspan(start_x - 0.5, end_x + 0.5, alpha=0.08, color="#f39c12", zorder=0)
        except Exception:
            pass

        # ── breakout vertical line ─────────────────────────────────────────────

        if c.breakout_date:
            bk_ts = pd.Timestamp(c.breakout_date)
            bk_x  = next((i for i, d in enumerate(dates_ts) if d >= bk_ts), None)
            if bk_x is not None:
                ax.axvline(x=bk_x, color="#f1c40f", linewidth=1.2, linestyle="-", alpha=0.7)

        # ── title & legend ─────────────────────────────────────────────────────

        ptype_label = c.pattern_type.replace("_", " ").title()
        bk_label    = c.breakout_type.replace("type", "Type ").title() if c.breakout_type != "pending" else "Pending"
        fig.suptitle(
            f"{c.ticker}  ·  {ptype_label}  ·  {bk_label}  ·  Score {c.score:.0f}/100",
            color="#d1d4dc", fontsize=13, fontweight="bold", y=1.01,
        )

        legend_items = [
            mpatches.Patch(color="#e67e22", label=f"Resistance {c.upper_bound:.2f}"),
            mpatches.Patch(color="#2980b9", label=f"Support {c.lower_bound:.2f}"),
            mpatches.Patch(color="#27ae60", label=f"Entry ~{c.entry_zone_low:.2f}"),
            mpatches.Patch(color="#e74c3c", label=f"Stop {c.stop_loss:.2f}"),
            mpatches.Patch(color="#8e44ad", label=f"Target {c.price_target:.2f} (+{c.measured_move_pct:.1f}%)"),
        ]
        ax.legend(handles=legend_items, loc="upper left", fontsize=8,
                  facecolor="#1e222d", edgecolor="#363a45", labelcolor="#d1d4dc")

        # ── save ───────────────────────────────────────────────────────────────

        fname = f"{c.ticker}_{c.pattern_type}_{c.pattern_end_date}.png"
        fpath = CHARTS_DIR / fname
        fig.savefig(fpath, dpi=130, bbox_inches="tight", facecolor="#131722")
        plt.close(fig)

        log.debug("Chart saved: %s", fpath)
        return fpath

    except Exception as e:
        log.warning("Chart generation failed for %s %s: %s", c.ticker, c.pattern_type, e)
        return None


def generate_all(candidates: list[PatternCandidate],
                 data: dict[str, pd.DataFrame]) -> int:
    """Generate charts for all candidates. Returns count of saved charts."""
    saved = 0
    for c in candidates:
        df = data.get(c.ticker)
        if df is None:
            continue
        path = generate(c, df)
        if path:
            saved += 1
    log.info("Charts saved: %d  →  %s", saved, CHARTS_DIR)
    return saved
