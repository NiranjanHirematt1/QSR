"""Multi-Timeframe Clock — the mechanism that makes cross-timeframe lookahead
structurally impossible.

The engine iterates the canonical *base* timeframe. Higher timeframes are
derived on the fly: base bars accumulate into the currently-forming higher bar,
which is emitted as *closed* only when the first base bar of the NEXT higher
bucket arrives. Consequently, while the strategy processes any base bar inside
higher-bucket k, only bucket k-1 (fully in the past) is ever visible. There is
no code path by which an unclosed higher bar can be observed.

Sub-daily buckets are epoch-anchored; daily-and-above buckets are anchored to
the instrument's session-day start (so a futures 'day' breaks correctly).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ...domain.instruments.session_calendar import SessionCalendar
from ...domain.market_data.candle import Candle
from ...domain.market_data.timeframe import Timeframe

_ONE_DAY = 86400


@dataclass
class _Accumulator:
    bucket: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def add(self, c: Candle) -> None:
        self.high = max(self.high, c.high)
        self.low = min(self.low, c.low)
        self.close = c.close
        self.volume += c.volume

    def to_candle(self, tf: Timeframe) -> Candle:
        return Candle(self.bucket, tf, self.open, self.high, self.low, self.close, self.volume)


class MultiTimeframeClock:
    """Advances the base series and emits closed higher-timeframe bars."""

    def __init__(
        self,
        base: Timeframe,
        higher: tuple[Timeframe, ...],
        calendar: SessionCalendar,
    ) -> None:
        self._base = base
        self._calendar = calendar
        # Only genuine higher timeframes (strict multiples, not the base itself).
        self._higher: tuple[Timeframe, ...] = tuple(
            tf for tf in sorted(set(higher), key=lambda t: t.seconds)
            if tf.seconds > base.seconds
        )
        for tf in self._higher:
            if not tf.is_multiple_of(base):
                raise ValueError(f"{tf.label} is not an integer multiple of base {base.label}")
        self._acc: dict[Timeframe, _Accumulator | None] = {tf: None for tf in self._higher}

    @property
    def higher_timeframes(self) -> tuple[Timeframe, ...]:
        return self._higher

    def _bucket(self, tf: Timeframe, ts: datetime) -> datetime:
        if tf.seconds < _ONE_DAY:
            return tf.floor(ts)
        return self._calendar.session_day_start(ts)

    def advance(self, base_bar: Candle) -> list[tuple[Timeframe, Candle]]:
        """Feed one closed base bar; return list of (timeframe, closed_bar) for
        every higher timeframe whose bar just completed (chronological, coarser
        last)."""
        closed: list[tuple[Timeframe, Candle]] = []
        for tf in self._higher:
            key = self._bucket(tf, base_bar.open_time)
            acc = self._acc[tf]
            if acc is None:
                self._acc[tf] = _Accumulator(key, base_bar.open, base_bar.high,
                                             base_bar.low, base_bar.close, base_bar.volume)
            elif key == acc.bucket:
                acc.add(base_bar)
            else:
                closed.append((tf, acc.to_candle(tf)))  # previous bucket now closed
                self._acc[tf] = _Accumulator(key, base_bar.open, base_bar.high,
                                             base_bar.low, base_bar.close, base_bar.volume)
        return closed
