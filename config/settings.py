import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Paths
TICKERS_CSV         = BASE_DIR / "config" / "tickers.csv"
TICKERS_EU_CSV      = BASE_DIR / "config" / "tickers_eu.csv"
TICKERS_NASDAQ_CSV  = BASE_DIR / "config" / "tickers_nasdaq100.csv"
TICKERS_SP500_CSV   = BASE_DIR / "config" / "tickers_sp500.csv"
TICKERS_RUSSELL_CSV = BASE_DIR / "config" / "tickers_russell.csv"
DB_PATH          = BASE_DIR / "db" / "aksel.db"
SIGNALS_DIR      = BASE_DIR / "signals" / "output"
SIGNALS_DIR.mkdir(parents=True, exist_ok=True)

# Data fetching
YFINANCE_INTERVAL   = "1wk"
YFINANCE_PERIOD     = "5y"

# Pattern detection thresholds
DETECTION_LOOKBACK_WEEKS = 156
MAX_PATTERN_WEEKS        = 52

SIGNAL_MAX_STALENESS_WEEKS  = 12
SIGNAL_MAX_BREAKOUT_WEEKS   = 8
SIGNAL_PRICE_PROXIMITY_PCT  = 0.15

RECTANGLE_TOLERANCE     = 0.02
RECTANGLE_MIN_WEEKS     = 6
RECTANGLE_MIN_TOUCHES   = 2

TRIANGLE_MIN_WEEKS      = 6
TRIANGLE_MAX_WEEKS      = 52
TRIANGLE_CONVERGENCE_R2 = 0.70

HS_SHOULDER_TOLERANCE   = 0.05

# Scoring weights (must sum to 1.0)
SCORE_PATTERN_QUALITY   = 0.40
SCORE_VOLUME_BREAKOUT   = 0.30
SCORE_BREAKOUT_TYPE     = 0.20
SCORE_HISTORICAL_RATE   = 0.10

VOLUME_LOOKBACK_WEEKS        = 20
BREAKOUT_VOLUME_FACTOR       = 1.5
BREAKOUT_CONFIRM_CLOSES      = 2

SCHEDULER_HOUR   = 6
SCHEDULER_MINUTE = 30

# Alerts (optional)
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ALERT_MIN_SCORE  = 70
