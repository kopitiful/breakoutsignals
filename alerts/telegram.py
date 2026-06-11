"""
Optional Telegram alerts — only fires for signals above ALERT_MIN_SCORE.
Set TELEGRAM_TOKEN and TELEGRAM_CHAT_ID in .env to activate.
"""

import logging
import requests

from config.settings import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, ALERT_MIN_SCORE
from detection.base import PatternCandidate

log = logging.getLogger(__name__)


def send_alerts(candidates: list[PatternCandidate]) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return

    high_quality = [c for c in candidates if c.score >= ALERT_MIN_SCORE]
    if not high_quality:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    for c in high_quality:
        msg = (
            f"*{c.ticker}* — {c.pattern_type.replace('_', ' ').title()}\n"
            f"Breakout: {c.breakout_type} | Score: {c.score}/100\n"
            f"Entry: {c.entry_zone_low:.2f}–{c.entry_zone_high:.2f}\n"
            f"SL: {c.stop_loss:.2f} | Target: {c.price_target:.2f} "
            f"(+{c.measured_move_pct:.1f}%)\n"
            f"Duration: {c.pattern_duration_weeks}w"
        )
        try:
            requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": msg,
                "parse_mode": "Markdown",
            }, timeout=10)
        except Exception as e:
            log.error("Telegram alert failed: %s", e)
