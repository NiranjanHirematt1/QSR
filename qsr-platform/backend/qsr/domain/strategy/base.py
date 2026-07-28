"""Python strategy authoring API (Phase 1 frontend).

``Strategy`` is a convenience base class for writing strategies in Python. It is
*not* what the engine depends on — the engine depends on
:class:`StrategyAdapter`. ``PythonStrategyAdapter`` bridges a ``Strategy`` to the
adapter port. Keeping authoring and the engine contract separate is exactly what
lets other languages plug in later: they provide their own adapter, and the
engine is none the wiser.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..market_data.timeframe import Timeframe
from ..orders.intents import (
    CloseIntent,
    OrderIntent,
    OrderType,
    Side,
    SizeSpec,
    StopLossIntent,
    TakeProfitIntent,
)
from .adapter import IndicatorRequest, StrategyAdapter, StrategyRequirements
from .context import StrategyContext


class Strategy(ABC):
    """Base class for Python-authored strategies.

    Subclasses declare requirements in :meth:`initialize` and act in
    :meth:`on_bar`, using the convenience helpers (``buy``/``sell``/``close``/
    ``set_stoploss``/``set_takeprofit``) which simply build and submit intents.
    """

    def __init__(self) -> None:
        self._ctx: StrategyContext | None = None

    # ---- lifecycle (override) ----------------------------------------------
    @abstractmethod
    def initialize(self) -> StrategyRequirements: ...

    @abstractmethod
    def on_bar(self) -> None: ...

    # ---- injected context ---------------------------------------------------
    @property
    def ctx(self) -> StrategyContext:
        if self._ctx is None:  # pragma: no cover - defensive
            raise RuntimeError("Strategy context accessed before bind()")
        return self._ctx

    def _bind(self, ctx: StrategyContext) -> None:
        self._ctx = ctx

    # ---- authoring helpers (thin wrappers over the intent IR) --------------
    def buy(self, size: SizeSpec | None = None, *, order_type: OrderType = OrderType.MARKET,
            limit: float | None = None, stop: float | None = None,
            tag: str | None = None, reason: str | None = None) -> None:
        self.ctx.submit(OrderIntent(Side.BUY, order_type, size, limit, stop, tag=tag, reason=reason))

    def sell(self, size: SizeSpec | None = None, *, order_type: OrderType = OrderType.MARKET,
             limit: float | None = None, stop: float | None = None,
             tag: str | None = None, reason: str | None = None) -> None:
        self.ctx.submit(OrderIntent(Side.SELL, order_type, size, limit, stop, tag=tag, reason=reason))

    def close(self, tag: str | None = None, *, qty: float | None = None,
              reason: str | None = None) -> None:
        self.ctx.submit(CloseIntent(tag=tag, qty=qty, reason=reason))

    def set_stoploss(self, *, price: float | None = None, ticks: float | None = None,
                     distance: float | None = None, trailing: bool = False,
                     tag: str | None = None) -> None:
        self.ctx.submit(StopLossIntent(price=price, ticks=ticks, distance=distance,
                                       trailing=trailing, tag=tag))

    def set_takeprofit(self, *, price: float | None = None, ticks: float | None = None,
                       distance: float | None = None, tag: str | None = None) -> None:
        self.ctx.submit(TakeProfitIntent(price=price, ticks=ticks, distance=distance, tag=tag))


class PythonStrategyAdapter(StrategyAdapter):
    """Bridges a Python :class:`Strategy` to the engine's adapter port."""

    def __init__(self, strategy: Strategy) -> None:
        self._strategy = strategy

    def initialize(self, ctx: StrategyContext) -> StrategyRequirements:
        self._strategy._bind(ctx)
        return self._strategy.initialize()

    def on_bar(self, ctx: StrategyContext) -> None:
        self._strategy._bind(ctx)
        self._strategy.on_bar()


__all__ = [
    "Strategy",
    "PythonStrategyAdapter",
    "IndicatorRequest",
    "StrategyRequirements",
]
