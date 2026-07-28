"""End-to-end engine tests with hand-verified numbers, determinism, no-lookahead."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from qsr.domain.instruments.catalog import es_future
from qsr.domain.market_data.timeframe import Timeframe
from qsr.domain.orders.intents import SizeKind, SizeSpec
from qsr.domain.strategy.adapter import IndicatorRequest, StrategyRequirements
from qsr.domain.strategy.base import PythonStrategyAdapter, Strategy
from qsr.engine.backtester import Backtester
from qsr.engine.config import BacktestConfig
from qsr.engine.execution.fill_model import IntrabarAssumption
from tests.engine_helpers import M5, series


class EnterOnce(Strategy):
    """Buy 1 contract on the first bar with a fixed TP/SL, then hold."""
    def __init__(self, tp=None, sl=None):
        super().__init__(); self.tp, self.sl = tp, sl
    def initialize(self):
        return StrategyRequirements(timeframes=(M5,))
    def on_bar(self):
        if self.ctx.position_qty == 0 and self.ctx.bar(M5).open_time == self._first:
            self.buy(SizeSpec(SizeKind.FIXED_QTY, 1), reason="enter")
            if self.tp: self.set_takeprofit(ticks=self.tp)
            if self.sl: self.set_stoploss(ticks=self.sl)
    def bind_first(self, ts): self._first = ts


def _run(strategy, candles, **cfg):
    strategy.bind_first(candles[0].open_time)
    bt = Backtester(es_future(), M5, BacktestConfig(close_at_end=True, **cfg))
    return bt.run(candles, PythonStrategyAdapter(strategy), strategy_id="t")


def test_market_entry_fills_next_bar_open_no_costs():
    # Entry signal on bar0 close -> fills at bar1 open (4000). Hold to end, close at last close.
    candles = series([(4000, 4001, 3999, 4000),   # bar0: signal
                      (4000, 4005, 3998, 4004),   # bar1: fill @ open 4000
                      (4004, 4010, 4003, 4008)])  # bar2 (last): close @ 4008
    res = _run(EnterOnce(), candles)
    assert res.trade_count == 1
    t = res.trades[0]
    assert t.entry_price == 4000.0
    assert t.exit_price == 4008.0
    assert t.pnl == pytest.approx((4008 - 4000) * 50)   # $400, no costs
    assert t.exit_reason == "end_of_data"


def test_take_profit_hit():
    # TP 40 ticks = +10 pts from entry 4000 -> 4010; bar2 high 4012 triggers.
    candles = series([(4000, 4001, 3999, 4000),
                      (4000, 4002, 3999, 4001),
                      (4001, 4012, 4000, 4008)])
    res = _run(EnterOnce(tp=40, sl=40), candles)
    t = res.trades[0]
    assert t.exit_price == 4010.0 and t.exit_reason == "target"
    assert t.pnl == pytest.approx((4010 - 4000) * 50)


def test_stop_loss_hit_with_slippage_and_r_multiple():
    # 1-tick slippage applies to BOTH sides: entry fills 4000.25, so the 40-tick
    # (10pt) stop sits at 3990.25; bar2 low 3988 triggers; exit fills 3990.25 - 0.25 = 3990.0.
    candles = series([(4000, 4001, 3999, 4000),
                      (4000, 4002, 3999, 4001),
                      (4001, 4003, 3988, 3990)])
    res = _run(EnterOnce(tp=200, sl=40), candles, slippage_ticks=1)
    t = res.trades[0]
    assert t.entry_price == pytest.approx(4000.25)
    assert t.exit_price == pytest.approx(3990.0) and t.exit_reason == "stop"
    # risk = |4000.25 - 3990.25| * 50 = $500; pnl = (3990.0-4000.25)*50 = -512.5 -> R = -1.025
    assert t.pnl == pytest.approx(-512.5)
    assert t.r_multiple == pytest.approx(-512.5 / 500.0, abs=1e-6)


def test_short_take_profit():
    class ShortOnce(EnterOnce):
        def on_bar(self):
            if self.ctx.position_qty == 0 and self.ctx.bar(M5).open_time == self._first:
                self.sell(SizeSpec(SizeKind.FIXED_QTY, 1), reason="short")
                self.set_takeprofit(ticks=40)  # target below for a short
    candles = series([(4000, 4001, 3999, 4000),
                      (4000, 4002, 3999, 4001),
                      (4001, 4002, 3988, 3992)])  # low 3988 <= 3990 target
    res = _run(ShortOnce(), candles)
    t = res.trades[0]
    assert t.exit_price == 4000.0 - 10 and t.exit_reason == "target"
    assert t.pnl == pytest.approx((4000 - 3990) * 50)  # short profit


def test_determinism_same_inputs_same_output():
    candles = series([(4000 + i, 4002 + i, 3998 + i, 4000 + i) for i in range(30)])
    r1 = _run(EnterOnce(tp=40, sl=40), candles, commission_per_unit=2, slippage_ticks=1)
    r2 = _run(EnterOnce(tp=40, sl=40), candles, commission_per_unit=2, slippage_ticks=1)
    assert r1.manifest.run_hash == r2.manifest.run_hash
    assert [(t.entry_price, t.exit_price, t.pnl) for t in r1.trades] == \
           [(t.entry_price, t.exit_price, t.pnl) for t in r2.trades]
    assert r1.final_equity == r2.final_equity


def test_equity_curve_recorded_each_bar():
    candles = series([(4000, 4001, 3999, 4000) for _ in range(10)])
    res = _run(EnterOnce(), candles)
    assert len(res.equity_curve) >= len(candles)
    assert res.equity_curve[0].equity == pytest.approx(100_000, abs=1e-6)


def test_cash_and_trade_pnl_reconcile():
    candles = series([(4000, 4005, 3995, 4000 + (3 if i % 2 else -2)) for i in range(40)])
    res = _run(EnterOnce(tp=40, sl=40), candles, commission_per_unit=2.0, slippage_ticks=1)
    gain = res.final_equity - 100_000
    assert res.net_profit == pytest.approx(gain, abs=1e-6)


class MtfStrategy(Strategy):
    """Requests an H1 indicator to exercise the multi-timeframe path."""
    def initialize(self):
        H1 = Timeframe.from_label("H1")
        return StrategyRequirements(timeframes=(M5, H1),
                                    indicators=(IndicatorRequest("sma", H1, (("period", 2),)),))
    def on_bar(self):
        pass


def test_multi_timeframe_run_smoke():
    candles = series([(4000 + i, 4002 + i, 3998 + i, 4001 + i) for i in range(60)])
    bt = Backtester(es_future(), M5, BacktestConfig())
    res = bt.run(candles, PythonStrategyAdapter(MtfStrategy()), strategy_id="mtf")
    assert len(res.equity_curve) >= 60  # ran without lookahead errors


class HigherTFAudit(Strategy):
    """Records, at every bar, the close_time of the visible H1 bar vs. now, to
    prove the strategy never sees an unclosed higher-timeframe bar."""
    def __init__(self):
        super().__init__(); self.violations = 0; self.saw_h1 = 0
    def initialize(self):
        self.H1 = Timeframe.from_label("H1")
        return StrategyRequirements(timeframes=(M5, self.H1))
    def on_bar(self):
        h1 = self.ctx.bar(self.H1)
        if h1 is not None:
            self.saw_h1 += 1
            # A visible higher bar must be fully in the past: it closed at or
            # before 'now' (the current base bar's close).
            if h1.close_time > self.ctx.now:
                self.violations += 1


def test_engine_never_exposes_unclosed_higher_bar():
    # 3 hours of M5 bars so several H1 bars form.
    candles = series([(4000 + i % 5, 4002 + i % 5, 3998 + i % 5, 4001 + i % 5)
                      for i in range(36 * 3)])
    strat = HigherTFAudit()
    Backtester(es_future(), M5, BacktestConfig()).run(
        candles, PythonStrategyAdapter(strat), strategy_id="audit")
    assert strat.saw_h1 > 0          # it did observe closed H1 bars
    assert strat.violations == 0     # ...and never an unclosed one
