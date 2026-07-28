"""Fill / Position / Trade records produced by the engine (read side of the IR).

These are emitted by the engine and consumed by analytics, the Trade Explorer,
and reporting. They are language-agnostic value objects too, so any UI or export
target can render them without knowing how a trade was generated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .intents import Side


@dataclass(frozen=True, slots=True)
class Fill:
    order_tag: str | None
    side: Side
    price: float
    qty: float
    commission: float
    slippage_ticks: float
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class Trade:
    """A closed round-trip, fully self-describing for the Trade Explorer."""

    instrument: str
    side: Side
    qty: float
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    pnl: float                     # cash, quote currency
    r_multiple: float | None       # PnL / initial risk
    commission: float
    entry_reason: str | None
    exit_reason: str | None
    mae: float | None = None       # max adverse excursion
    mfe: float | None = None       # max favourable excursion
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def duration_seconds(self) -> float:
        return (self.exit_time - self.entry_time).total_seconds()

    @property
    def is_win(self) -> bool:
        return self.pnl > 0
