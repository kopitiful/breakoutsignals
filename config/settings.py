import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Paths
TICKERS_CSV      = BASE_DIR / "config" / "tickers.csv"
TICKERS_EU_CSV   = BASE_DIR / "config" / "tickers_eu.csv"
DB_PATH          = BASE_DIR / "db" / "aksel.db"
SIGNALS_DIR      = BASE_DIR / "signals" / "output"
SIGNALS_DIR.mkdir(parents=True, exist_ok=True)

# Data fetching
YFINANCE_INTERVAL   = "1wk"
YFINANCE_PERIOD     = "5y"          # enough history for pattern detection

# Pattern detection thresholds
DETECTION_LOOKBACK_WEEKS = 156      # only scan last 3 years of data per ticker
MAX_PATTERN_WEEKS        = 52       # cap pattern duration at 1 year

# Relevance filter — discard patterns too far in the past
# "pending":  pattern must have ended within this many weeks of the last bar
# "breakout": breakout must have occurred within this many weeks
SIGNAL_MAX_STALENESS_WEEKS  = 12   # pending pattern must have ended within 12 weeks
SIGNAL_MAX_BREAKOUT_WEEKS   = 8    # type1/2 breakout must be within 8 weeks
# Price still inside pattern (pending): must be within this % of pattern height from boundary
SIGNAL_PRICE_PROXIMITY_PCT  = 0.15  # 15% — allows price near apex of triangle

RECTANGLE_TOLERANCE     = 0.02      # ±2% band tolerance
RECTANGLE_MIN_WEEKS     = 6
RECTANGLE_MIN_TOUCHES   = 2         # per side

TRIANGLE_MIN_WEEKS      = 6
TRIANGLE_MAX_WEEKS      = 52        # skip windows longer than 1 year
TRIANGLE_CONVERGENCE_R2 = 0.70      # minimum R² for trendlines to count

HS_SHOULDER_TOLERANCE   = 0.05      # right shoulder ≤5% off left shoulder height

# Scoring weights (must sum to 1.0)
SCORE_PATTERN_QUALITY   = 0.40
SCORE_VOLUME_BREAKOUT   = 0.30
SCORE_BREAKOUT_TYPE     = 0.20
SCORE_HISTORICAL_RATE   = 0.10

VOLUME_LOOKBACK_WEEKS        = 20   # for breakout volume comparison
BREAKOUT_VOLUME_FACTOR       = 1.5  # breakout bar must be ≥ this × 20w avg
BREAKOUT_CONFIRM_CLOSES      = 2    # consecutive closes outside boundary needed

# Scheduler — runs daily at 06:30 UTC
SCHEDULER_HOUR   = 6
SCHEDULER_MINUTE = 30

# Alerts (optional)
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ALERT_MIN_SCORE  = 70               # only alert on high-quality signals
