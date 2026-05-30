from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, Float, Integer,
    Date, DateTime, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, Session
from config.settings import DB_PATH


class Base(DeclarativeBase):
    pass


class PriceBar(Base):
    """Weekly OHLCV cache — one row per ticker/date."""
    __tablename__ = "price_bars"
    __table_args__ = (UniqueConstraint("ticker", "date"),)

    id         = Column(Integer, primary_key=True, autoincrement=True)
    ticker     = Column(String, nullable=False, index=True)
    date       = Column(Date, nullable=False, index=True)
    open       = Column(Float)
    high       = Column(Float)
    low        = Column(Float)
    close      = Column(Float)
    volume     = Column(Float)
    fetched_at = Column(DateTime, default=datetime.utcnow)


class Signal(Base):
    """Detected pattern signals with breakout classification."""
    __tablename__ = "signals"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    ticker                = Column(String, nullable=False, index=True)
    pattern_type          = Column(String, nullable=False)   # rectangle / triangle_asc / triangle_desc / triangle_sym / hs / ihs
    breakout_type         = Column(String)                   # type1 / type2 / type3 / type4 / pending
    confirmed             = Column(String, default="pending") # full / volume / time / none / pending
    breakout_date         = Column(Date)
    pattern_start_date    = Column(Date)
    pattern_end_date      = Column(Date)
    pattern_duration_weeks = Column(Integer)
    upper_bound           = Column(Float)
    lower_bound           = Column(Float)
    entry_zone_low        = Column(Float)
    entry_zone_high       = Column(Float)
    stop_loss             = Column(Float)
    price_target          = Column(Float)
    measured_move_pct     = Column(Float)
    score                 = Column(Float)
    status                = Column(String, default="active")  # active / expired / triggered
    created_at            = Column(DateTime, default=datetime.utcnow)


def get_engine():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{DB_PATH}", echo=False)


def init_db():
    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


def get_session(engine=None) -> Session:
    if engine is None:
        engine = get_engine()
    return Session(engine)
