"""
yfinance batch fetcher with SQLite cache.

Flow:
  1. Read tickers from CSV, skip known-dead symbols
  2. For each ticker check last cached bar date
  3. Only download tickers whose cache is stale or empty
  4. Tickers that return no data are written to db/dead_tickers.txt — never retried
  5. Upsert new bars into price_bars table
  6. Return a dict {ticker: pd.DataFrame} for all tickers
"""

import logging
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf
from sqlalchemy import select, func

from config.settings import TICKERS_CSV, TICKERS_EU_CSV, YFINANCE_INTERVAL, YFINANCE_PERIOD
from db.models import PriceBar, get_session, init_db

log = logging.getLogger(__name__)

# Silence yfinance's own ERROR spam for delisted / unknown symbols
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

DEAD_TICKERS_FILE = Path(__file__).resolve().parent.parent / "db" / "dead_tickers.txt"


# ── Dead-ticker list ────────────────────────────────────────────────────────

def _load_dead() -> set[str]:
    if not DEAD_TICKERS_FILE.exists():
        return set()
    return {t.strip().upper() for t in DEAD_TICKERS_FILE.read_text().splitlines() if t.strip()}


def _save_dead(dead: set[str]) -> None:
    DEAD_TICKERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEAD_TICKERS_FILE.write_text("\n".join(sorted(dead)) + "\n")


def mark_dead(tickers: list[str]) -> None:
    """Add tickers to the permanent skip list and log them."""
    if not tickers:
        return
    dead = _load_dead()
    new = set(tickers) - dead
    if new:
        dead |= new
        _save_dead(dead)
        log.info("Marked %d symbols as dead (no data): %s", len(new), ", ".join(sorted(new)))


# ── Ticker loading ──────────────────────────────────────────────────────────

def load_tickers(csv_path=None) -> list[str]:
    path = csv_path or TICKERS_CSV
    df = pd.read_csv(path, header=None, names=["ticker"])
    all_tickers = df["ticker"].dropna().str.strip().str.upper().tolist()
    # drop junk entries (non-alphanumeric, too long) and known-dead symbols
    valid = [
        t for t in all_tickers
        if t.replace("-", "").replace(".", "").isalnum() and len(t) <= 12
    ]
    dead = _load_dead()
    skipped = [t for t in valid if t in dead]
    if skipped:
        log.debug("Skipping %d known-dead symbols.", len(skipped))
    return [t for t in valid if t not in dead]


# ── Cache freshness ─────────────────────────────────────────────────────────

def _last_completed_week_start() -> date:
    """
    Monday of the most recently completed trading week.
    Sat/Sun → this week's Monday (week just closed).
    Mon–Fri → last week's Monday (current week still open).
    """
    today = date.today()
    weekday = today.weekday()   # Mon=0 … Sun=6
    if weekday >= 5:
        return today - timedelta(days=weekday)
    else:
        return today - timedelta(days=weekday + 7)


def _stale_tickers(tickers: list[str], session) -> list[str]:
    cutoff = _last_completed_week_start()
    stale = []
    for ticker in tickers:
        last_date = session.scalar(
            select(func.max(PriceBar.date)).where(PriceBar.ticker == ticker)
        )
        if last_date is None or last_date < cutoff:
            stale.append(ticker)
    return stale


# ── Download ────────────────────────────────────────────────────────────────

def _download_batch(tickers: list[str]) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """
    Download weekly bars for a list of tickers.
    Returns (data_dict, dead_list) where dead_list contains symbols with no data.
    """
    if not tickers:
        return {}, []

    log.info("Downloading %d tickers from yfinance ...", len(tickers))
    raw = yf.download(
        tickers=tickers,
        period=YFINANCE_PERIOD,
        interval=YFINANCE_INTERVAL,
        group_by="ticker",
        auto_adjust=True,
        progress=False,
        threads=True,
    )

    result: dict[str, pd.DataFrame] = {}
    dead: list[str] = []

    for ticker in tickers:
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                # Multi-ticker batch: level 0 = ticker, level 1 = field
                # Single-ticker:      level 0 = field,  level 1 = ticker
                if ticker in raw.columns.get_level_values(0):
                    df = raw[ticker].copy()
                else:
                    df = raw.xs(ticker, axis=1, level=1).copy()
            else:
                df = raw.copy()

            df.columns = [c.lower() for c in df.columns]
            df.index   = pd.to_datetime(df.index).date
            df = df.dropna(subset=["close"])
            if df.empty:
                dead.append(ticker)
            else:
                result[ticker] = df
        except (KeyError, AttributeError):
            dead.append(ticker)

    # If ALL tickers failed, this is a network/rate-limit error — don't mark as dead
    if dead and not result:
        log.warning("All %d tickers returned empty — likely a rate limit. Skipping dead-marking.", len(dead))
        return {}, []

    if dead:
        log.info("No data for %d symbols (will be skipped in future): %s",
                 len(dead), ", ".join(dead[:10]) + ("..." if len(dead) > 10 else ""))

    return result, dead


# ── Upsert / load ───────────────────────────────────────────────────────────

def _upsert_bars(ticker: str, df: pd.DataFrame, session) -> None:
    existing_dates = set(
        row[0] for row in session.execute(
            select(PriceBar.date).where(PriceBar.ticker == ticker)
        )
    )
    new_bars = [
        PriceBar(
            ticker=ticker,
            date=idx,
            open=row.get("open"),
            high=row.get("high"),
            low=row.get("low"),
            close=row.get("close"),
            volume=row.get("volume"),
        )
        for idx, row in df.iterrows()
        if idx not in existing_dates
    ]
    if new_bars:
        session.add_all(new_bars)
        log.debug("Inserted %d new bars for %s", len(new_bars), ticker)


def _load_from_cache(tickers: list[str], session) -> dict[str, pd.DataFrame]:
    result = {}
    for ticker in tickers:
        rows = session.execute(
            select(PriceBar)
            .where(PriceBar.ticker == ticker)
            .order_by(PriceBar.date)
        ).scalars().all()

        if not rows:
            continue

        result[ticker] = pd.DataFrame(
            [
                {
                    "date":   r.date,
                    "open":   r.open,
                    "high":   r.high,
                    "low":    r.low,
                    "close":  r.close,
                    "volume": r.volume,
                }
                for r in rows
            ]
        ).set_index("date")

    return result


# ── Main entry point ────────────────────────────────────────────────────────

def fetch_all(tickers: list[str] | None = None) -> dict[str, pd.DataFrame]:
    """
    Returns {ticker: weekly_ohlcv_df} for all live tickers.
    Refreshes stale entries, skips dead symbols permanently.
    """
    engine = init_db()

    if tickers is None:
        tickers = load_tickers()

    with get_session(engine) as session:
        stale = _stale_tickers(tickers, session)

        if stale:
            downloaded, dead = _download_batch(stale)
            mark_dead(dead)
            for ticker, df in downloaded.items():
                _upsert_bars(ticker, df, session)
            session.commit()
            log.info("Cache updated for %d tickers (%d dead skipped).",
                     len(downloaded), len(dead))
        else:
            log.info("All %d tickers are fresh in cache.", len(tickers))

        live_tickers = [t for t in tickers if t not in _load_dead()]
        data = _load_from_cache(live_tickers, session)

    log.info("Loaded data for %d/%d tickers.", len(data), len(tickers))
    return data
