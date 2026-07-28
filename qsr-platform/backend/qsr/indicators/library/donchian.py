"""Donchian Channel: highest high / lowest low over the window."""
from __future__ import annotations

from collections import deque

from ...domain.market_data.candle import Candle
from ..base import Indicator
from ..outputs import BandsValue


class DonchianChannel(Indicator):
    name = "donchian"

    def __init__(self, period: int = 20) -> None:
        super().__init__(period=period)
        self._period = int(period)
        self._highs: deque[float] = deque(maxlen=self._period)
        self._lows: deque[float] = deque(maxlen=self._period)

    @property
    def warmup_period(self) -> int:
        return self._period

    def _on_bar(self, candle: Candle) -> BandsValue | None:
        self._highs.append(candle.high)
        self._lows.append(candle.low)
        if len(self._highs) < self._period:
            return None
        upper = max(self._highs)
        lower = min(self._lows)
        return BandsValue(upper=upper, middle=(upper + lower) / 2.0, lower=lower)
