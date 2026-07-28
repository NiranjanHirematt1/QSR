"""StrategyAdapter port — the language-agnostic boundary the engine drives.

The engine knows *only* this interface. It calls :meth:`initialize` once and
:meth:`on_bar` for every closed base bar, passing a :class:`StrategyContext`.
The adapter turns some underlying representation of a strategy into intents on
that context.

Concrete adapters (each a single new file, engine untouched):

* ``PythonStrategyAdapter``  -> wraps a Python ``Strategy`` subclass (Phase 1).
* ``PineScriptAdapter``      -> compiles Pine source to intents (future).
* ``VisualBuilderAdapter``   -> interprets a node graph to intents (future).
* ``AIStrategyAdapter``      -> queries a model for intents (future).
* ``RemoteStrategyAdapter``  -> bridges an out-of-process runtime over JSON
                                using the OrderIntent IR (any language, future).

Because the contract is expressed in terms of the serialisable OrderIntent IR
and the StrategyContext Protocol, none of these require changes to the engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..market_data.timeframe import Timeframe
from .context import StrategyContext


@dataclass(frozen=True, slots=True)
class StrategyRequirements:
    """What a strategy declares it needs at initialize() time.

    The engine uses this to wire up the multi-timeframe clock and indicator
    streams *before* the run starts, so ``on_bar`` never triggers lazy work that
    could accidentally peek at future data.
    """

    timeframes: tuple[Timeframe, ...]
    indicators: tuple["IndicatorRequest", ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class IndicatorRequest:
    name: str
    timeframe: Timeframe
    params: tuple[tuple[str, float], ...] = field(default_factory=tuple)
    alias: str | None = None
    """Optional handle name. Lets a strategy reference two indicators of the same
    type/timeframe (e.g. EMA(10) and EMA(30)) distinctly. Defaults to ``name``."""

    @property
    def handle(self) -> str:
        return self.alias or self.name


@runtime_checkable
class StrategyAdapter(Protocol):
    """The single strategy interface the engine depends on."""

    def initialize(self, ctx: StrategyContext) -> StrategyRequirements:
        """Declare required timeframes/indicators and set up internal state."""
        ...

    def on_bar(self, ctx: StrategyContext) -> None:
        """Called once per closed base bar; emit intents via ``ctx.submit``."""
        ...
