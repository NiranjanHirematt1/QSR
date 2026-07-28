"""Volume-Weighted Moving Average: sum(close*vol)/sum(vol) over the window."""
from __future__ import annotations

from ...domain.market_data.candle import Candle
from ..base import Indicator
from ._smoothing import Rolling


class VWMA(Indicator):
    name = "vwma"

    def __init__(self, period: int = 14) -> None:
        super().__init__(period=period)
        self._period = int(period)
        self._pv = Rolling(self._period)   # price*volume
        self._vol = Rolling(self._period)  # volume

    @property
    def warmup_period(self) -> int:
        return self._period

    def _on_bar(self, candle: Candle) -> float | None:
        self._pv.update(candle.close * candle.volume)
        self._vol.update(candle.volume)
        if not self._vol.full:
            return None
        vol_sum = sum(self._vol.values)
        if vol_sum == 0:
            return None  # undefined when the window has no volume
        return sum(self._pv.values) / vol_sum
