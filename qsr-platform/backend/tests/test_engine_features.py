"""Feature coverage: limit/stop entries, trailing stops, partial closes,
live stop adjustment, pyramiding, and the read-only context surface."""
from __future__ import annotations

import pytest

from qsr.domain.instruments.catalog import es_future
from qsr.domain.market_data.timeframe import Timeframe
from qsr.domain.orders.intents import OrderType, SizeKind, SizeSpec
from qsr.domain.strategy.adapter import IndicatorRequest, StrategyRequirements
from qsr.domain.strategy.base import PythonStrategyAdapter, Strategy
from qsr.engine.backtester import Backtester
from qsr.engine.config import BacktestConfig
from tests.engine_helpers import M5, series


class OneShot(Strategy):
    """Runs a single `action(self)` on the first bar only."""
    def __init__(self, action):
        super().__init__(); self._action = action; self._done = False
    def initialize(self):
        return StrategyRequirements(timeframes=(M5,))
    def on_bar(self):
        if not self._done:
            self._action(self); self._done = True


def _bt(candles, action, **cfg):
    bt = Backtester(es_future(), M5, BacktestConfig(**cfg))
    return bt.run(candles, PythonStrategyAdapter(OneShot(action)), strategy_id="feat")


def test_limit_entry_fills_on_dip():
    candles = series([(4000, 4001, 3999, 4000),
                      (4000, 4001, 3994, 3998),   # low 3994 <= limit 3995 -> fill 3995
                      (3998, 4005, 3997, 4004)])
    res = _bt(candles, lambda s: s.buy(SizeSpec(SizeKind.FIXED_QTY, 1),
                                       order_type=OrderType.LIMIT, limit=3995, reason="lim"))
    assert res.trades[0].entry_price == pytest.approx(3995.0)


def test_stop_entry_fills_on_breakout():
    candles = series([(4000, 4001, 3999, 4000),
                      (4000, 4006, 3999, 4005),   # high 4006 >= stop 4004 -> fill 4004
                      (4005, 4010, 4004, 4008)])
    res = _bt(candles, lambda s: s.buy(SizeSpec(SizeKind.FIXED_QTY, 1),
                                       order_type=OrderType.STOP, stop=4004, reason="brk"))
    assert res.trades[0].entry_price == pytest.approx(4004.0)


def test_trailing_stop_ratchets_and_exits():
    candles = series([(4000, 4001, 3999, 4000),   # signal
                      (4000, 4003, 3999, 4002),   # fill @4000; stop 3995 -> ratchet 3997
                      (4002, 4008, 4001, 4006),   # no exit; ratchet -> 4001
                      (4006, 4007, 3999, 4000)])  # low 3999 <= 4001 -> trailing stop hit @4001
    res = _bt(candles, lambda s: (s.buy(SizeSpec(SizeKind.FIXED_QTY, 1), reason="t"),
                                  s.set_stoploss(ticks=20, trailing=True)))
    t = res.trades[0]
    assert t.exit_reason == "stop" and t.exit_price == pytest.approx(4001.0)


def test_partial_close_produces_two_trades():
    candles = series([(4000, 4001, 3999, 4000)] +
                     [(4000, 4002, 3998, 4001) for _ in range(4)])

    class Partial(Strategy):
        def __init__(self): super().__init__(); self._n = 0
        def initialize(self): return StrategyRequirements(timeframes=(M5,))
        def on_bar(self):
            self._n += 1
            if self._n == 1:
                self.buy(SizeSpec(SizeKind.FIXED_QTY, 2), reason="in")
            elif self._n == 3:
                self.close(qty=1, reason="scale_out")
    bt = Backtester(es_future(), M5, BacktestConfig())
    res = bt.run(candles, PythonStrategyAdapter(Partial()), strategy_id="p")
    assert res.trade_count == 2
    assert {t.exit_reason for t in res.trades} == {"scale_out", "end_of_data"}
    assert sum(t.qty for t in res.trades) == 2


def test_adjust_stop_on_live_position():
    candles = series([(4000, 4001, 3999, 4000),
                      (4000, 4002, 3999, 4001),   # fill @4000
                      (4001, 4002, 3999, 4001),   # set stop 4000.5 (live)
                      (4001, 4002, 3990, 3995)])  # low 3990 <= 4000.5 -> stop

    class Adjust(Strategy):
        def __init__(self): super().__init__(); self._n = 0
        def initialize(self): return StrategyRequirements(timeframes=(M5,))
        def on_bar(self):
            self._n += 1
            if self._n == 1:
                self.buy(SizeSpec(SizeKind.FIXED_QTY, 1), reason="in")
            elif self._n == 3:
                self.set_stoploss(price=4000.5)   # tighten on the live position
    bt = Backtester(es_future(), M5, BacktestConfig())
    res = bt.run(candles, PythonStrategyAdapter(Adjust()), strategy_id="adj")
    assert res.trades[0].exit_reason == "stop"
    assert res.trades[0].exit_price == pytest.approx(4000.5)


def test_pyramiding_adds_to_position():
    candles = series([(4000, 4001, 3999, 4000)] +
                     [(4000, 4002, 3998, 4001) for _ in range(3)])

    class Pyramid(Strategy):
        def __init__(self): super().__init__(); self._n = 0
        def initialize(self): return StrategyRequirements(timeframes=(M5,))
        def on_bar(self):
            self._n += 1
            if self._n in (1, 2):
                self.buy(SizeSpec(SizeKind.FIXED_QTY, 1), reason="add")
    bt = Backtester(es_future(), M5, BacktestConfig())
    res = bt.run(candles, PythonStrategyAdapter(Pyramid()), strategy_id="py")
    # two entries add to one net position of 2, closed once at end
    assert res.trade_count == 1 and res.trades[0].qty == 2


def test_context_history_and_indicator_readonly():
    captured = {}

    class Reader(Strategy):
        def initialize(self):
            return StrategyRequirements(
                timeframes=(M5,),
                indicators=(IndicatorRequest("sma", M5, (("period", 3),)),))
        def on_bar(self):
            captured["hist"] = len(self.ctx.history(M5, 3))
            captured["sma"] = self.ctx.indicator("sma", M5)
            captured["eq"] = self.ctx.equity
            captured["cash"] = self.ctx.cash
    candles = series([(4000 + i, 4001 + i, 3999 + i, 4000 + i) for i in range(6)])
    bt = Backtester(es_future(), M5, BacktestConfig())
    bt.run(candles, PythonStrategyAdapter(Reader()), strategy_id="r")
    assert captured["hist"] == 3          # history capped at requested n
    assert captured["sma"] is not None    # indicator warmed up and readable
    assert captured["cash"] == 100_000
