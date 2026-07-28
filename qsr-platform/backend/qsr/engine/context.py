"""Concrete engine-side StrategyContext.

Implements the :class:`StrategyContext` port. It exposes only *closed* bars and
read-only portfolio state, and collects the intents a strategy emits. The
strategy has no other handle on the engine, so lookahead is impossible by
construction.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any, Sequence

from ..domain.market_data.candle import Candle
from ..domain.market_data.timeframe import Timeframe
from ..indicators.engine import IndicatorHandle
from .execution.broker import BrokerSimulator

_MAX_HISTORY = 5000


class EngineStrategyContext:
    def __init__(self, broker: BrokerSimulator) -> None:
        self._broker = broker
        self._now: datetime | None = None
        self._mark: float = 0.0
        self._history: dict[str, deque[Candle]] = {}
        self._indicators: dict[tuple[str, str], IndicatorHandle] = {}
        self._intents: list[Any] = []
        self.logs: list[str] = []

    # ---- engine-side wiring (not part of the strategy port) -----------------
    def register_indicator(self, name: str, tf: Timeframe, handle: IndicatorHandle) -> None:
        self._indicators[(name, tf.label)] = handle

    def push_bar(self, tf: Timeframe, candle: Candle) -> None:
        self._history.setdefault(tf.label, deque(maxlen=_MAX_HISTORY)).append(candle)

    def set_clock(self, now: datetime, mark: float) -> None:
        self._now, self._mark = now, mark

    def drain_intents(self) -> list[Any]:
        out, self._intents = self._intents, []
        return out

    # ---- StrategyContext port ----------------------------------------------
    @property
    def now(self) -> datetime:
        assert self._now is not None
        return self._now

    def bar(self, timeframe: Timeframe) -> Candle | None:
        h = self._history.get(timeframe.label)
        return h[-1] if h else None

    def history(self, timeframe: Timeframe, n: int) -> Sequence[Candle]:
        h = self._history.get(timeframe.label)
        if not h:
            return ()
        return tuple(h)[-n:]

    def indicator(self, name: str, timeframe: Timeframe) -> Any:
        handle = self._indicators.get((name, timeframe.label))
        return handle.value if handle is not None else None

    @property
    def position_qty(self) -> float:
        return self._broker.position.qty

    @property
    def equity(self) -> float:
        return self._broker.equity(self._mark)

    @property
    def cash(self) -> float:
        return self._broker.realized_cash

    def submit(self, intent: Any) -> None:
        self._intents.append(intent)

    def log(self, message: str) -> None:
        self.logs.append(message)
