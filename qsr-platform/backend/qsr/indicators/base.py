"""Incremental indicator interface + auto-registration.

Every indicator is a *stateful streaming* object: it is fed one closed
:class:`Candle` at a time via :meth:`update`, updates O(1) internal state, and
returns its current value (or ``None`` while warming up). Because the only input
channel is a closed bar and there is no method to look ahead, lookahead bias is
structurally impossible.

Subclasses set a class-level ``name``; ``__init_subclass__`` then registers them
automatically, so adding an indicator is exactly one new file — no central list
to edit.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from ..domain.market_data.candle import Candle

# Global registry, populated at import time by __init_subclass__.
INDICATOR_REGISTRY: dict[str, type["Indicator"]] = {}


class Indicator(ABC):
    """Base class for all incremental indicators."""

    #: Unique registry key. Empty base/private classes are not registered.
    name: ClassVar[str] = ""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        key = getattr(cls, "name", "")
        if not key:
            return  # abstract/intermediate class — do not register
        existing = INDICATOR_REGISTRY.get(key)
        if existing is not None and existing is not cls:
            raise ValueError(
                f"Duplicate indicator name {key!r}: {existing.__name__} vs {cls.__name__}"
            )
        INDICATOR_REGISTRY[key] = cls

    def __init__(self, **params: float) -> None:
        self._params: dict[str, float] = dict(params)
        self._value: Any = None
        self._count: int = 0

    # ---- public state -------------------------------------------------------
    @property
    def params(self) -> dict[str, float]:
        return dict(self._params)

    @property
    def value(self) -> Any:
        """Current output, or ``None`` while warming up."""
        return self._value

    @property
    def is_ready(self) -> bool:
        return self._value is not None

    @property
    def bars_seen(self) -> int:
        return self._count

    @property
    @abstractmethod
    def warmup_period(self) -> int:
        """Number of bars required before the indicator can produce a value."""

    # ---- streaming update ---------------------------------------------------
    def update(self, candle: Candle) -> Any:
        """Feed one closed bar; returns the current value (may be ``None``)."""
        self._count += 1
        self._value = self._on_bar(candle)
        return self._value

    @abstractmethod
    def _on_bar(self, candle: Candle) -> Any:
        """Compute new state/value from ``candle``. Return value or ``None``."""

    # ---- identity (used for request de-duplication) -------------------------
    def canonical_params(self) -> tuple[tuple[str, float], ...]:
        return tuple(sorted(self._params.items()))

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        p = ", ".join(f"{k}={v}" for k, v in self.canonical_params())
        return f"{type(self).__name__}({p})"
