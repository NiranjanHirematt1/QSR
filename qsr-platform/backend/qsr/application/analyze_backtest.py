"""Bridge a BacktestResult into an analytics PerformanceReport.

Lives in the application layer so the pure analytics package never needs to know
about the engine's EquityPoint type.
"""
from __future__ import annotations

from ..analytics.periodicity import Periodicity
from ..analytics.report import PerformanceReport
from ..domain.market_data.timeframe import Timeframe
from ..engine.result import BacktestResult
from ..reporting.context import ReportContext


def report_from_result(result: BacktestResult, base_timeframe: Timeframe,
                       periodicity: Periodicity | None = None) -> PerformanceReport:
    equity = [(p.timestamp, p.equity) for p in result.equity_curve]
    return PerformanceReport.build(result.trades, equity, base_timeframe.seconds, periodicity)


def context_from_result(result: BacktestResult, base_timeframe: Timeframe,
                        title: str | None = None,
                        periodicity: Periodicity | None = None) -> ReportContext:
    report = report_from_result(result, base_timeframe, periodicity)
    equity = [(p.timestamp, p.equity) for p in result.equity_curve]
    return ReportContext(
        title=title or f"{result.manifest.strategy_id} · {result.manifest.instrument}",
        manifest=result.manifest.to_dict(),
        report=report,
        trades=result.trades,
        equity=equity,
    )
