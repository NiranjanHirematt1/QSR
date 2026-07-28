"""Relative Strength Index (Wilder). RSI = 100 - 100/(1+RS)."""
from __future__ import annotations

from ...domain.market_data.candle import Candle
from ..base import Indicator
from ._smoothing import WilderMA


class RSI(Indicator):
    name = "rsi"

    def __init__(self, period: int = 14) -> None:
        super().__init__(period=period)
        self._period = int(period)
        self._gain = WilderMA(self._period)
        self._loss = WilderMA(self._period)
        self._prev_close: float | None = None

    @property
    def warmup_period(self) -> int:
        # Need one prior close to form the first change, then `period` changes.
        return self._period + 1

    def _on_bar(self, candle: Candle) -> float | None:
        close = candle.close
        if self._prev_close is None:
            self._prev_close = close
            return None
        change = close - self._prev_close
        self._prev_close = close
        avg_gain = self._gain.update(max(change, 0.0))
        avg_loss = self._loss.update(max(-change, 0.0))
        if avg_gain is None or avg_loss is None:
            return None
        if avg_loss == 0.0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - 100.0 / (1.0 + rs)
