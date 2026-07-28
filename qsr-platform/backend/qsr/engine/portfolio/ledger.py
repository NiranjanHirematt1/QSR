"""Trade ledger and equity curve — the read side consumed by analytics/reports."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ...domain.orders.trade import Trade


@dataclass(frozen=True, slots=True)
class EquityPoint:
    timestamp: datetime
    equity: float
    cash: float
    position_qty: float


@dataclass(slots=True)
class Ledger:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[EquityPoint] = field(default_factory=list)

    def record_trade(self, trade: Trade) -> None:
        self.trades.append(trade)

    def record_equity(self, point: EquityPoint) -> None:
        self.equity_curve.append(point)

    @property
    def final_equity(self) -> float:
        return self.equity_curve[-1].equity if self.equity_curve else 0.0
