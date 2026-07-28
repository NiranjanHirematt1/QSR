"""SuperTrend: ATR-based trailing trend indicator.

Bands:
    hl2         = (high + low) / 2
    basic_upper = hl2 + multiplier * ATR
    basic_lower = hl2 - multiplier * ATR
Final bands carry over unless price breaks them:
    final_upper = basic_upper if basic_upper < prev_final_upper or prev_close > prev_final_upper else prev_final_upper
    final_lower = basic_lower if basic_lower > prev_final_lower or prev_close < prev_final_lower else prev_final_lower
The line flips between the final lower band (uptrend, direction +1) and final
upper band (downtrend, direction -1) as close crosses the active band.
"""
from __future__ import annotations

from ...domain.market_data.candle import Candle
from ..base import Indicator
from ..outputs import SuperTrendValue
from ._smoothing import WilderMA
from .atr import true_range


class SuperTrend(Indicator):
    name = "supertrend"

    def __init__(self, period: int = 10, multiplier: float = 3.0) -> None:
        super().__init__(period=period, multiplier=multiplier)
        self._period = int(period)
        self._mult = float(multiplier)
        self._atr = WilderMA(self._period)
        self._prev_close: float | None = None
        self._final_upper: float | None = None
        self._final_lower: float | None = None
        self._supertrend: float | None = None
        self._direction: int = -1

    @property
    def warmup_period(self) -> int:
        return self._period + 1

    def _on_bar(self, candle: Candle) -> SuperTrendValue | None:
        h, l, c = candle.high, candle.low, candle.close
        # First bar seeds prev_close only (true range needs a prior close).
        if self._prev_close is None:
            self._prev_close = c
            return None
        tr = true_range(h, l, self._prev_close)
        atr = self._atr.update(tr)
        prev_close = self._prev_close
        self._prev_close = c
        if atr is None:
            return None

        hl2 = (h + l) / 2.0
        basic_upper = hl2 + self._mult * atr
        basic_lower = hl2 - self._mult * atr

        if self._supertrend is None:
            # First ready bar: initialise bands and pick a starting trend.
            self._final_upper = basic_upper
            self._final_lower = basic_lower
            if c <= basic_upper:
                self._supertrend, self._direction = basic_upper, -1
            else:
                self._supertrend, self._direction = basic_lower, 1
            return SuperTrendValue(self._supertrend, self._direction)

        pfu = self._final_upper
        pfl = self._final_lower
        pc = prev_close if prev_close is not None else c
        final_upper = basic_upper if (basic_upper < pfu or pc > pfu) else pfu  # type: ignore[operator]
        final_lower = basic_lower if (basic_lower > pfl or pc < pfl) else pfl  # type: ignore[operator]

        if self._supertrend == pfu:  # was following the upper band (downtrend)
            supertrend = final_upper if c <= final_upper else final_lower
        else:                        # was following the lower band (uptrend)
            supertrend = final_lower if c >= final_lower else final_upper

        self._final_upper, self._final_lower = final_upper, final_lower
        self._supertrend = supertrend
        self._direction = 1 if supertrend == final_lower else -1
        return SuperTrendValue(supertrend, self._direction)
