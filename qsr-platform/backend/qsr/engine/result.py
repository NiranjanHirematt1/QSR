"""BacktestResult — the immutable output bundle of a run."""
from __future__ import annotations

from dataclasses import dataclass

from ..domain.orders.trade import Trade
from .manifest import RunManifest
from .portfolio.ledger import EquityPoint, Ledger


@dataclass(frozen=True, slots=True)
class BacktestResult:
    manifest: RunManifest
    ledger: Ledger

    @property
    def trades(self) -> list[Trade]:
        return self.ledger.trades

    @property
    def equity_curve(self) -> list[EquityPoint]:
        return self.ledger.equity_curve

    @property
    def final_equity(self) -> float:
        return self.ledger.final_equity

    @property
    def trade_count(self) -> int:
        return len(self.ledger.trades)

    @property
    def net_profit(self) -> float:
        return sum(t.pnl for t in self.ledger.trades)
