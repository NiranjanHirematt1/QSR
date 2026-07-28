"""Exponential Moving Average (SMA-seeded, standard TA convention)."""
from __future__ import annotations

from ...domain.market_data.candle import Candle
from ..base import Indicator
from ._smoothing import EmaCore


class EMA(Indicator):
    name = "ema"

    def __init__(self, period: int = 14) -> None:
        super().__init__(period=period)
        self._period = int(period)
        self._core = EmaCore(self._period)

    @property
    def warmup_period(self) -> int:
        return self._period

    def _on_bar(self, candle: Candle) -> float | None:
        return self._core.update(candle.close)
