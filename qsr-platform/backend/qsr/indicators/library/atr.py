"""Average True Range (Wilder)."""
from __future__ import annotations

from ...domain.market_data.candle import Candle
from ..base import Indicator
from ._smoothing import WilderMA


def true_range(high: float, low: float, prev_close: float | None) -> float:
    if prev_close is None:
        return high - low
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


class ATR(Indicator):
    name = "atr"

    def __init__(self, period: int = 14) -> None:
        super().__init__(period=period)
        self._period = int(period)
        self._wilder = WilderMA(self._period)
        self._prev_close: float | None = None

    @property
    def warmup_period(self) -> int:
        return self._period + 1

    def _on_bar(self, candle: Candle) -> float | None:
        # True range needs a prior close (Wilder convention); the first bar only
        # seeds prev_close and emits nothing. This makes readiness == warmup.
        if self._prev_close is None:
            self._prev_close = candle.close
            return None
        tr = true_range(candle.high, candle.low, self._prev_close)
        self._prev_close = candle.close
        return self._wilder.update(tr)
