"""
APScheduler entry point — runs the pipeline daily at 06:30 UTC.
Start with: python scheduler.py
"""

import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import SCHEDULER_HOUR, SCHEDULER_MINUTE
from pipeline import run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("aksel.log"),
    ],
)
log = logging.getLogger(__name__)


def main():
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        run,
        trigger=CronTrigger(hour=SCHEDULER_HOUR, minute=SCHEDULER_MINUTE),
        id="aksel_daily",
        name="Aksel Pattern Detection",
        misfire_grace_time=3600,
    )
    log.info(
        "Scheduler started — runs daily at %02d:%02dZ. Press Ctrl+C to stop.",
        SCHEDULER_HOUR, SCHEDULER_MINUTE,
    )
    try:
        scheduler.start()
    except KeyboardInterrupt:
        log.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
