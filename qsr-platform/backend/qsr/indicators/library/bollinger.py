"""Bollinger Bands: SMA middle band +/- k * population standard deviation."""
from __future__ import annotations

from math import sqrt

from ...domain.market_data.candle import Candle
from ..base import Indicator
from ..outputs import BandsValue
from ._smoothing import Rolling


class BollingerBands(Indicator):
    name = "bollinger"

    def __init__(self, period: int = 20, k: float = 2.0) -> None:
        super().__init__(period=period, k=k)
        self._period = int(period)
        self._k = float(k)
        self._roll = Rolling(self._period)

    @property
    def warmup_period(self) -> int:
        return self._period

    def _on_bar(self, candle: Candle) -> BandsValue | None:
        self._roll.update(candle.close)
        if not self._roll.full:
            return None
        vals = self._roll.values
        mean = sum(vals) / self._period
        var = sum((v - mean) ** 2 for v in vals) / self._period  # population
        sd = sqrt(var)
        return BandsValue(upper=mean + self._k * sd, middle=mean, lower=mean - self._k * sd)
