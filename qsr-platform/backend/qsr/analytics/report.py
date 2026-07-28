"""PerformanceReport — the aggregate analytics bundle for a backtest."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from ..domain.orders.trade import Trade
from .periodicity import Periodicity
from .risk_metrics import RiskMetrics, compute_risk_metrics, monthly_returns
from .trade_metrics import TradeMetrics, compute_trade_metrics, pnl_distribution

EquitySeries = Sequence[tuple[datetime, float]]


@dataclass(frozen=True, slots=True)
class PerformanceReport:
    trades: TradeMetrics
    risk: RiskMetrics
    monthly_returns: dict[str, float]
    distribution: list[dict]

    def to_dict(self) -> dict:
        return {
            "trades": self.trades.to_dict(),
            "risk": self.risk.to_dict(),
            "monthly_returns": self.monthly_returns,
            "distribution": self.distribution,
        }

    @classmethod
    def build(cls, trades: Sequence[Trade], equity: EquitySeries,
              base_timeframe_seconds: int,
              periodicity: Periodicity | None = None) -> "PerformanceReport":
        tm = compute_trade_metrics(trades)
        ppy = (periodicity or Periodicity()).periods_per_year(base_timeframe_seconds)
        rm = compute_risk_metrics(equity, tm.net_profit, ppy)
        return cls(
            trades=tm,
            risk=rm,
            monthly_returns=monthly_returns(equity),
            distribution=pnl_distribution(trades),
        )
