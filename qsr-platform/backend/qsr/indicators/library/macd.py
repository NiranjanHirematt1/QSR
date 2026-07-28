"""Moving Average Convergence Divergence.

MACD line  = EMA(fast) - EMA(slow) of close
Signal     = EMA(signal) of the MACD line
Histogram  = MACD - Signal
"""
from __future__ import annotations

from ...domain.market_data.candle import Candle
from ..base import Indicator
from ..outputs import MACDValue
from ._smoothing import EmaCore


class MACD(Indicator):
    name = "macd"

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9) -> None:
        if fast >= slow:
            raise ValueError("MACD requires fast < slow")
        super().__init__(fast=fast, slow=slow, signal=signal)
        self._fast = EmaCore(int(fast))
        self._slow = EmaCore(int(slow))
        self._signal = EmaCore(int(signal))
        self._slow_p = int(slow)
        self._signal_p = int(signal)

    @property
    def warmup_period(self) -> int:
        # slow EMA ready at `slow` bars; signal then needs `signal` MACD values.
        return self._slow_p + self._signal_p - 1

    def _on_bar(self, candle: Candle) -> MACDValue | None:
        f = self._fast.update(candle.close)
        s = self._slow.update(candle.close)
        if f is None or s is None:
            return None
        macd_line = f - s
        sig = self._signal.update(macd_line)
        if sig is None:
            return None
        return MACDValue(macd=macd_line, signal=sig, histogram=macd_line - sig)
