"""Runnable end-to-end example: generate data, backtest a library strategy, report.

Run from the backend directory:  python examples/ema_crossover.py

This demonstrates the full headless pipeline (no API/UI): build candles, run the
registered ``ema_crossover`` strategy through the engine with realistic costs,
compute analytics, and export an HTML report. It uses the *real* library
strategy, not a re-implementation, so it stays correct as the strategy evolves.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from qsr.application.analyze_backtest import context_from_result
from qsr.domain.instruments.catalog import es_future
from qsr.domain.market_data.candle import Candle
from qsr.domain.market_data.timeframe import Timeframe
from qsr.domain.strategy.base import PythonStrategyAdapter
from qsr.engine.backtester import Backtester
from qsr.engine.config import BacktestConfig
from qsr.reporting.html_exporter import HtmlExporter
from qsr.strategies import registry as strategy_registry

M5 = Timeframe.from_label("M5")


def _demo_candles(n: int = 500) -> list[Candle]:
    """Deterministic oscillating series so the crossover strategy trades."""
    start = datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc)
    candles = []
    for i in range(n):
        mid = 4000 + 40 * math.sin(i / 30)
        o = mid
        c = mid + math.sin(i)
        h = max(o, c) + 1.0
        low = min(o, c) - 1.0
        candles.append(Candle(start + timedelta(minutes=5 * i), M5, o, h, low, c, 1000.0))
    return candles


def main() -> None:
    candles = _demo_candles()
    strategy = strategy_registry.create("ema_crossover", {"fast": 10, "slow": 30})
    result = Backtester(es_future(), M5, BacktestConfig(commission_per_unit=2.0, slippage_ticks=1)).run(
        candles, PythonStrategyAdapter(strategy), strategy_id="ema_crossover")

    ctx = context_from_result(result, M5, title="EMA crossover · ES · M5")
    m = ctx.report.trades
    avg_r = m.avg_r if m.avg_r is None else round(m.avg_r, 2)
    print(f"trades={m.count}  net={m.net_profit:,.2f}  win_rate={m.win_rate:.1%}  "
          f"avg_R={avg_r}  maxDD={ctx.report.risk.max_drawdown_pct:.2f}%")

    out = HtmlExporter().export(ctx, Path("ema_crossover_report"))
    print(f"HTML report written to {out}")


if __name__ == "__main__":
    main()
