"""
Signal writer: persists PatternCandidates to SQLite and daily CSV.
"""

import csv
import logging
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select, func

from config.settings import SIGNALS_DIR
from db.models import Signal, get_session, init_db
from detection.base import PatternCandidate

log = logging.getLogger(__name__)

CSV_FIELDS = [
    "ticker", "pattern_type", "breakout_type", "confirmed", "breakout_date",
    "entry_zone_low", "entry_zone_high", "stop_loss", "price_target",
    "measured_move_pct", "pattern_duration_weeks", "score", "status",
    "pattern_start_date", "pattern_end_date",
]


def _to_signal(c: PatternCandidate) -> Signal:
    return Signal(
        ticker=c.ticker,
        pattern_type=c.pattern_type,
        breakout_type=c.breakout_type,
        confirmed=c.confirmed,
        breakout_date=c.breakout_date,
        pattern_start_date=c.pattern_start_date,
        pattern_end_date=c.pattern_end_date,
        pattern_duration_weeks=c.pattern_duration_weeks,
        upper_bound=c.upper_bound,
        lower_bound=c.lower_bound,
        entry_zone_low=c.entry_zone_low,
        entry_zone_high=c.entry_zone_high,
        stop_loss=c.stop_loss,
        price_target=c.price_target,
        measured_move_pct=c.measured_move_pct,
        score=c.score,
        status=c.status,
    )


def save_signals(candidates: list[PatternCandidate], run_date: date | None = None) -> int:
    """Write candidates to DB and CSV. Returns count of saved signals."""
    if not candidates:
        return 0

    run_date = run_date or date.today()
    engine = init_db()
    today  = datetime.now(timezone.utc)

    with get_session(engine) as session:
        for c in candidates:
            # Find earliest existing entry for this exact signal pattern
            first_seen = session.scalar(
                select(func.min(Signal.created_at))
                .where(
                    Signal.ticker             == c.ticker,
                    Signal.pattern_type       == c.pattern_type,
                    Signal.pattern_start_date == c.pattern_start_date,
                )
            )
            if first_seen is None:
                first_seen = today
            # Store days-since-first-seen on the candidate for display
            c.first_seen_days = (today.date() - first_seen.date()
                                 if hasattr(first_seen, "date")
                                 else (today.date() - first_seen)).days

            session.add(_to_signal(c))

        session.commit()

    _write_csv(candidates, run_date)
    log.info("Saved %d signals for %s", len(candidates), run_date)
    return len(candidates)


def _write_csv(candidates: list[PatternCandidate], run_date: date) -> Path:
    path = SIGNALS_DIR / f"signals_{run_date}.csv"

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for c in candidates:
            writer.writerow({field: getattr(c, field, "") for field in CSV_FIELDS})

    log.info("CSV written: %s", path)
    return path
