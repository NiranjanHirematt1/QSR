"""Simple Moving Average."""
from __future__ import annotations

from ...domain.market_data.candle import Candle
from ..base import Indicator
from ._smoothing import Rolling


class SMA(Indicator):
    name = "sma"

    def __init__(self, period: int = 14) -> None:
        super().__init__(period=period)
        self._period = int(period)
        self._roll = Rolling(self._period)

    @property
    def warmup_period(self) -> int:
        return self._period

    def _on_bar(self, candle: Candle) -> float | None:
        return self._roll.update(candle.close)
