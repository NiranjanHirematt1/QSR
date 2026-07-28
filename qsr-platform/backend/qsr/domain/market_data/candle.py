"""Candle (OHLCV bar) value object."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .timeframe import Timeframe


@dataclass(frozen=True, slots=True)
class Candle:
    """A single immutable OHLCV bar.

    Invariants (validated on construction):
      * timestamps are timezone-aware UTC
      * ``low <= open, close <= high`` and ``low <= high``
      * volume is non-negative

    ``open_time`` is the inclusive start of the bar; ``close_time`` is the
    exclusive end (``open_time + timeframe``). A bar is only "closed" — and
    therefore visible to a strategy — once simulated time has passed
    ``close_time``. This single rule is what prevents lookahead bias.
    """

    open_time: datetime
    timeframe: Timeframe
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        if self.open_time.tzinfo is None:
            raise ValueError("Candle.open_time must be timezone-aware (UTC)")
        if self.open_time.utcoffset().total_seconds() != 0:  # type: ignore[union-attr]
            raise ValueError("Candle.open_time must be in UTC")
        hi, lo = self.high, self.low
        if lo > hi:
            raise ValueError(f"Invalid OHLC: low {lo} > high {hi} @ {self.open_time}")
        if not (lo <= self.open <= hi):
            raise ValueError(f"Invalid OHLC: open {self.open} outside [{lo}, {hi}] @ {self.open_time}")
        if not (lo <= self.close <= hi):
            raise ValueError(f"Invalid OHLC: close {self.close} outside [{lo}, {hi}] @ {self.open_time}")
        if self.volume < 0:
            raise ValueError(f"Invalid volume {self.volume} @ {self.open_time}")

    @property
    def close_time(self) -> datetime:
        """Exclusive end of the bar."""
        return self.open_time + self.timeframe.delta

    @property
    def is_bullish(self) -> bool:
        return self.close >= self.open

    @property
    def range(self) -> float:
        return self.high - self.low
