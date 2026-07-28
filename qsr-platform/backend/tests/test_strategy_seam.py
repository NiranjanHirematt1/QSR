"""Proves the language-agnostic seam: a Python strategy emits portable intents
through the StrategyContext port, with no reference to the engine."""
from __future__ import annotations

from datetime import datetime, timezone

from qsr.domain.market_data.timeframe import Timeframe
from qsr.domain.orders.intents import OrderIntent, Side, SizeKind, SizeSpec
from qsr.domain.strategy.adapter import StrategyRequirements
from qsr.domain.strategy.base import PythonStrategyAdapter, Strategy

H1 = Timeframe.from_label("H1")


class _RecordingContext:
    """Minimal in-memory StrategyContext double capturing intents."""
    def __init__(self):
        self.intents = []
        self.logs = []
    now = datetime(2024, 1, 2, tzinfo=timezone.utc)
    def bar(self, tf): ...
    def history(self, tf, n): return []
    def indicator(self, name, tf): return None
    position_qty = 0.0
    equity = 10_000.0
    cash = 10_000.0
    def submit(self, intent): self.intents.append(intent)
    def log(self, msg): self.logs.append(msg)


class _DemoStrategy(Strategy):
    def initialize(self) -> StrategyRequirements:
        return StrategyRequirements(timeframes=(H1,))
    def on_bar(self) -> None:
        self.buy(SizeSpec(SizeKind.RISK_PERCENT, 1.0), reason="breakout")
        self.set_stoploss(ticks=15)


def test_python_strategy_emits_portable_intents():
    ctx = _RecordingContext()
    adapter = PythonStrategyAdapter(_DemoStrategy())
    reqs = adapter.initialize(ctx)
    assert reqs.timeframes == (H1,)

    adapter.on_bar(ctx)
    order = ctx.intents[0]
    assert isinstance(order, OrderIntent)
    assert order.side is Side.BUY
    assert order.size.kind is SizeKind.RISK_PERCENT
    assert order.reason == "breakout"          # "why" captured for Trade Explorer
    # intents are plain value objects -> serialisable -> language agnostic
    assert order.size.value == 1.0
