"""ReportContext + serialization helpers shared by all exporters."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from ..analytics.report import PerformanceReport
from ..domain.orders.trade import Trade


def trade_to_dict(t: Trade) -> dict:
    return {
        "instrument": t.instrument,
        "side": t.side.value,
        "qty": t.qty,
        "entry_time": t.entry_time.isoformat(),
        "exit_time": t.exit_time.isoformat(),
        "entry_price": t.entry_price,
        "exit_price": t.exit_price,
        "pnl": t.pnl,
        "r_multiple": t.r_multiple,
        "commission": t.commission,
        "entry_reason": t.entry_reason,
        "exit_reason": t.exit_reason,
        "duration_seconds": t.duration_seconds,
        "tags": list(t.tags),
    }


@dataclass(frozen=True, slots=True)
class ReportContext:
    title: str
    manifest: dict
    report: PerformanceReport
    trades: Sequence[Trade]
    equity: Sequence[tuple[datetime, float]]

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "manifest": self.manifest,
            "performance": self.report.to_dict(),
            "trades": [trade_to_dict(t) for t in self.trades],
            "equity_curve": [[ts.isoformat(), eq] for ts, eq in self.equity],
        }
