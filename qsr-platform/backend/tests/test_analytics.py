"""Analytics tests: hand-computed trade & risk metrics, edge cases, integration."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isclose, sqrt

import pytest

from qsr.analytics.periodicity import Periodicity
from qsr.analytics.report import PerformanceReport
from qsr.analytics.risk_metrics import (
    compute_risk_metrics,
    drawdown_curve,
    monthly_returns,
    period_returns,
    sharpe_ratio,
)
from qsr.analytics.trade_metrics import compute_trade_metrics, pnl_distribution
from qsr.domain.orders.intents import Side
from qsr.domain.orders.trade import Trade

T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _trade(pnl, r=None, win=None, minutes=60):
    return Trade(instrument="ES", side=Side.BUY, qty=1,
                 entry_time=T0, exit_time=T0 + timedelta(minutes=minutes),
                 entry_price=100, exit_price=100 + pnl, pnl=pnl, r_multiple=r,
                 commission=0.0, entry_reason="x", exit_reason="y")


def test_trade_metrics_hand_values():
    trades = [_trade(100, r=1.0), _trade(-50, r=-0.5), _trade(200, r=2.0), _trade(-50, r=-0.5)]
    m = compute_trade_metrics(trades)
    assert m.count == 4 and m.wins == 2 and m.losses == 2
    assert m.net_profit == 200
    assert m.gross_profit == 300 and m.gross_loss == -100
    assert m.win_rate == 0.5
    assert m.profit_factor == pytest.approx(3.0)      # 300 / 100
    assert m.avg_win == 150 and m.avg_loss == -50
    assert m.largest_win == 200 and m.largest_loss == -50
    assert m.expectancy == pytest.approx(50.0)        # 200/4
    assert m.avg_r == pytest.approx(0.5)              # (1-0.5+2-0.5)/4


def test_consecutive_streaks():
    trades = [_trade(1), _trade(1), _trade(-1), _trade(1), _trade(1), _trade(1), _trade(-1)]
    m = compute_trade_metrics(trades)
    assert m.max_consecutive_wins == 3
    assert m.max_consecutive_losses == 1


def test_profit_factor_none_when_no_losses():
    m = compute_trade_metrics([_trade(10), _trade(20)])
    assert m.profit_factor is None
    assert m.avg_loss is None and m.largest_loss is None


def test_empty_trades():
    m = compute_trade_metrics([])
    assert m.count == 0 and m.net_profit == 0 and m.profit_factor is None


def test_distribution_buckets():
    trades = [_trade(p) for p in (-10, -5, 0.0001, 5, 10)]
    dist = pnl_distribution(trades, bins=5)
    assert sum(b["count"] for b in dist) == 5
    assert len(dist) == 5


def test_drawdown_and_recovery():
    # equity: 100 -> 120 -> 90 -> 130. Peak 120, trough 90 -> max DD = 25% (abs 30).
    eq = [(T0 + timedelta(days=i), v) for i, v in enumerate([100, 120, 90, 130])]
    dd = drawdown_curve(eq)
    assert min(p.drawdown_abs for p in dd) == -30
    m = compute_risk_metrics(eq, net_profit=30, periods_per_year=252)
    assert m.max_drawdown_pct == pytest.approx(25.0)
    assert m.max_drawdown_abs == pytest.approx(30.0)
    assert m.recovery_factor == pytest.approx(30 / 30)   # net/maxDD_abs = 1.0


def test_sharpe_hand_value():
    # returns [0.1, 0.1, 0.1] -> stdev 0 -> None
    assert sharpe_ratio([0.1, 0.1, 0.1], 252) is None
    rets = [0.01, -0.02, 0.03]
    # population stdev used; verify formula direction
    s = sharpe_ratio(rets, 252)
    from statistics import fmean, pstdev
    expected = fmean(rets) / pstdev(rets) * sqrt(252)
    assert s == pytest.approx(expected)


def test_period_returns():
    eq = [(T0, 100.0), (T0, 110.0), (T0, 99.0)]
    r = period_returns(eq)
    assert r[0] == pytest.approx(0.1) and r[1] == pytest.approx(-0.1)


def test_monthly_returns():
    eq = [(datetime(2024, 1, 5, tzinfo=timezone.utc), 100.0),
          (datetime(2024, 1, 31, tzinfo=timezone.utc), 110.0),
          (datetime(2024, 2, 28, tzinfo=timezone.utc), 121.0)]
    mr = monthly_returns(eq)
    assert mr["2024-01"] == pytest.approx(0.10)   # 110/100 - 1
    assert mr["2024-02"] == pytest.approx(0.10)   # 121/110 - 1


def test_periodicity_factor():
    p = Periodicity(trading_days_per_year=252, hours_per_day=24)
    # M5 (300s): 252*24*3600/300
    assert p.periods_per_year(300) == pytest.approx(252 * 24 * 3600 / 300)


def test_report_integration_with_backtest():
    from qsr.domain.instruments.catalog import es_future
    from qsr.domain.market_data.timeframe import Timeframe
    from qsr.domain.orders.intents import SizeKind, SizeSpec
    from qsr.domain.strategy.adapter import StrategyRequirements
    from qsr.domain.strategy.base import PythonStrategyAdapter, Strategy
    from qsr.engine.backtester import Backtester
    from qsr.engine.config import BacktestConfig
    from qsr.application.analyze_backtest import report_from_result
    from tests.engine_helpers import M5, series

    class Flip(Strategy):
        def __init__(self): super().__init__(); self._n = 0
        def initialize(self): return StrategyRequirements(timeframes=(M5,))
        def on_bar(self):
            self._n += 1
            if self.ctx.position_qty == 0:
                self.buy(SizeSpec(SizeKind.FIXED_QTY, 1), reason="in")
                self.set_takeprofit(ticks=20); self.set_stoploss(ticks=20)
    candles = series([(4000, 4006, 3994, 4000 + (4 if i % 3 else -3)) for i in range(60)])
    res = Backtester(es_future(), M5, BacktestConfig()).run(
        candles, PythonStrategyAdapter(Flip()), strategy_id="flip")
    rep = report_from_result(res, M5)
    assert rep.trades.count >= 1
    # analytics net profit must match the ledger's
    assert rep.trades.net_profit == pytest.approx(res.net_profit)
    d = rep.to_dict()
    assert "trades" in d and "risk" in d and "monthly_returns" in d
