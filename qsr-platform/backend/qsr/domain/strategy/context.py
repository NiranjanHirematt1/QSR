"""StrategyContext port — the only surface a strategy may touch.

The context is a *read-only* view plus an *intent sink*. A strategy queries
closed bars and indicator values, inspects read-only portfolio state, and emits
intents. It can never reach into engine internals, mutate a position, or see an
unclosed bar. No-lookahead is therefore enforced structurally, at the API
boundary, rather than relying on the strategy author's discipline.

This is a Protocol, not a class: any runtime (in-process Python, or an
out-of-process bridge to another language) can satisfy it.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol, Sequence, runtime_checkable

from ..market_data.candle import Candle
from ..market_data.timeframe import Timeframe
from ..orders.intents import (
    CloseIntent,
    OrderIntent,
    StopLossIntent,
    TakeProfitIntent,
)


@runtime_checkable
class StrategyContext(Protocol):
    """Read-only market/portfolio view + intent sink handed to a strategy."""

    # ---- time ---------------------------------------------------------------
    @property
    def now(self) -> datetime:
        """Simulated close-time of the current base bar."""
        ...

    # ---- market data (only ever CLOSED bars) --------------------------------
    def bar(self, timeframe: Timeframe) -> Candle:
        """Latest *closed* bar for ``timeframe``."""
        ...

    def history(self, timeframe: Timeframe, n: int) -> Sequence[Candle]:
        """Last ``n`` closed bars for ``timeframe`` (oldest first)."""
        ...

    def indicator(self, name: str, timeframe: Timeframe) -> float | None:
        """Current value of a declared indicator, or ``None`` if warming up."""
        ...

    # ---- portfolio (read only) ----------------------------------------------
    @property
    def position_qty(self) -> float: ...

    @property
    def equity(self) -> float: ...

    @property
    def cash(self) -> float: ...

    # ---- intent sink --------------------------------------------------------
    def submit(
        self,
        intent: OrderIntent | CloseIntent | StopLossIntent | TakeProfitIntent,
    ) -> None:
        """Queue an intent for the engine to execute."""
        ...

    def log(self, message: str) -> None: ...
