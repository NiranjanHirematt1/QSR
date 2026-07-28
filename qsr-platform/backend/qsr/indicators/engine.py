"""IndicatorEngine — shared, de-duplicated indicator computation.

Multiple strategies (or multiple parts of one strategy) frequently request the
*same* indicator on the *same* stream — e.g. ``EMA(200)`` on H1. Computing it
twice is wasted work and a subtle source of divergence. The engine caches by a
canonical key ``(name, stream, sorted-params)`` so identical requests share one
streaming instance. Distinct params or streams get distinct instances.

A "stream" is an opaque identifier for a bar series (in Phase 1, typically a
timeframe label such as ``"H1"``). The engine feeds each closed bar for a stream
to exactly the indicators bound to that stream — once — preserving the
no-lookahead guarantee end to end.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..domain.market_data.candle import Candle
from . import registry
from .base import Indicator

_Key = tuple[str, str, tuple[tuple[str, float], ...]]


@dataclass(frozen=True, slots=True)
class IndicatorHandle:
    """Stable reference to a (possibly shared) indicator instance."""

    key: _Key
    _engine: "IndicatorEngine" = field(repr=False)

    @property
    def value(self) -> Any:
        return self._engine.instance(self).value

    @property
    def is_ready(self) -> bool:
        return self._engine.instance(self).is_ready

    @property
    def warmup_period(self) -> int:
        return self._engine.instance(self).warmup_period


class IndicatorEngine:
    def __init__(self) -> None:
        self._instances: dict[_Key, Indicator] = {}
        self._by_stream: dict[str, list[_Key]] = {}

    # ---- registration -------------------------------------------------------
    def request(self, name: str, stream: str, **params: float) -> IndicatorHandle:
        """Register (or reuse) an indicator on a stream. Identical requests
        return a handle to the *same* underlying instance."""
        probe = registry.create(name, **params)  # validates name/params early
        key: _Key = (name, stream, probe.canonical_params())
        if key not in self._instances:
            self._instances[key] = probe
            self._by_stream.setdefault(stream, []).append(key)
        return IndicatorHandle(key, self)

    # ---- streaming ----------------------------------------------------------
    def on_bar(self, stream: str, candle: Candle) -> None:
        """Feed a closed bar to every indicator bound to ``stream``."""
        for key in self._by_stream.get(stream, ()):
            self._instances[key].update(candle)

    # ---- access -------------------------------------------------------------
    def instance(self, handle: IndicatorHandle) -> Indicator:
        return self._instances[handle.key]

    def value(self, handle: IndicatorHandle) -> Any:
        return self._instances[handle.key].value

    @property
    def instance_count(self) -> int:
        return len(self._instances)

    def streams(self) -> tuple[str, ...]:
        return tuple(self._by_stream)
