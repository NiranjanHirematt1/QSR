"""RSI mean-reversion: buy oversold, exit on recovery."""
from __future__ import annotations

from qsr.domain.market_data.timeframe import Timeframe
from qsr.domain.orders.intents import SizeKind, SizeSpec
from qsr.domain.strategy.adapter import IndicatorRequest, StrategyRequirements
from qsr.strategies.base import ParamSpec, RegisteredStrategy


class RsiReversion(RegisteredStrategy):
    name = "rsi_reversion"
    params_schema = (
        ParamSpec("period", 14, description="RSI period"),
        ParamSpec("oversold", 30, description="Entry threshold"),
        ParamSpec("exit_level", 55, description="Exit threshold"),
        ParamSpec("risk_pct", 1.0, description="Risk per trade (% of equity)"),
        ParamSpec("stop_ticks", 120, description="Initial stop distance in ticks"),
        ParamSpec("timeframe_seconds", 300, description="Bar timeframe in seconds"),
    )

    def __init__(self, period: int = 14, oversold: float = 30, exit_level: float = 55,
                 risk_pct: float = 1.0, stop_ticks: float = 120,
                 timeframe_seconds: int = 300) -> None:
        super().__init__()
        self.period = int(period)
        self.oversold, self.exit_level = oversold, exit_level
        self.risk_pct, self.stop_ticks = risk_pct, stop_ticks
        self.tf = Timeframe(int(timeframe_seconds))

    def initialize(self) -> StrategyRequirements:
        return StrategyRequirements(
            timeframes=(self.tf,),
            indicators=(IndicatorRequest("rsi", self.tf, (("period", self.period),), alias="rsi"),),
        )

    def on_bar(self) -> None:
        rsi = self.ctx.indicator("rsi", self.tf)
        if rsi is None:
            return
        if self.ctx.position_qty == 0 and rsi < self.oversold:
            self.buy(SizeSpec(SizeKind.RISK_PERCENT, self.risk_pct), reason=f"rsi_{rsi:.0f}_oversold")
            self.set_stoploss(ticks=self.stop_ticks)
        elif self.ctx.position_qty > 0 and rsi > self.exit_level:
            self.close(reason=f"rsi_{rsi:.0f}_recovered")
