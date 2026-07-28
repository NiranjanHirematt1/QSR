"""EMA crossover: go long when fast EMA crosses above slow EMA, flat on cross down.

Uses aliased indicator requests so the two EMAs (same type + timeframe, different
period) are addressable independently through the context.
"""
from __future__ import annotations

from qsr.domain.market_data.timeframe import Timeframe
from qsr.domain.orders.intents import SizeKind, SizeSpec
from qsr.domain.strategy.adapter import IndicatorRequest, StrategyRequirements
from qsr.strategies.base import ParamSpec, RegisteredStrategy


class EmaCrossover(RegisteredStrategy):
    name = "ema_crossover"
    params_schema = (
        ParamSpec("fast", 10, description="Fast EMA period"),
        ParamSpec("slow", 30, description="Slow EMA period"),
        ParamSpec("risk_pct", 1.0, description="Risk per trade (% of equity)"),
        ParamSpec("stop_ticks", 100, description="Initial stop distance in ticks"),
        ParamSpec("timeframe_seconds", 300, description="Bar timeframe in seconds"),
    )

    def __init__(self, fast: int = 10, slow: int = 30, risk_pct: float = 1.0,
                 stop_ticks: float = 100, timeframe_seconds: int = 300) -> None:
        super().__init__()
        self.fast, self.slow = int(fast), int(slow)
        self.risk_pct, self.stop_ticks = risk_pct, stop_ticks
        self.tf = Timeframe(int(timeframe_seconds))
        self._prev_diff: float | None = None

    def initialize(self) -> StrategyRequirements:
        return StrategyRequirements(
            timeframes=(self.tf,),
            indicators=(
                IndicatorRequest("ema", self.tf, (("period", self.fast),), alias="fast"),
                IndicatorRequest("ema", self.tf, (("period", self.slow),), alias="slow"),
            ),
        )

    def on_bar(self) -> None:
        fast = self.ctx.indicator("fast", self.tf)
        slow = self.ctx.indicator("slow", self.tf)
        if fast is None or slow is None:
            return
        diff = fast - slow
        prev = self._prev_diff
        self._prev_diff = diff
        if prev is None:
            return
        crossed_up = prev <= 0 < diff
        crossed_down = prev >= 0 > diff
        if crossed_up and self.ctx.position_qty == 0:
            self.buy(SizeSpec(SizeKind.RISK_PERCENT, self.risk_pct), reason="ema_cross_up")
            self.set_stoploss(ticks=self.stop_ticks)
        elif crossed_down and self.ctx.position_qty > 0:
            self.close(reason="ema_cross_down")
