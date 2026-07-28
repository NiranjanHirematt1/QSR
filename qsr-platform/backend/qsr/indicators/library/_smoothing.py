"""Private numerical primitives shared by several indicators.

These are NOT indicators (no ``name`` attribute) so the registry's discovery
skips this module. Centralising the seeding conventions here guarantees that
EMA, RSI, ATR and ADX all agree on how smoothing is initialised.
"""
from __future__ import annotations

from collections import deque


class Rolling:
    """Fixed-length rolling window with O(1) sum, for simple moving averages."""

    __slots__ = ("period", "_buf", "_sum")

    def __init__(self, period: int) -> None:
        if period < 1:
            raise ValueError("period must be >= 1")
        self.period = period
        self._buf: deque[float] = deque(maxlen=period)
        self._sum = 0.0

    def update(self, x: float) -> float | None:
        if len(self._buf) == self.period:
            self._sum -= self._buf[0]  # value about to be evicted
        self._buf.append(x)
        self._sum += x
        return self.mean

    @property
    def full(self) -> bool:
        return len(self._buf) == self.period

    @property
    def mean(self) -> float | None:
        return self._sum / self.period if self.full else None

    @property
    def values(self) -> tuple[float, ...]:
        return tuple(self._buf)


class EmaCore:
    """Exponential moving average seeded with the SMA of the first ``period``
    inputs (the standard TA convention). Ready on the ``period``-th input."""

    __slots__ = ("period", "alpha", "_seed", "_ema")

    def __init__(self, period: int) -> None:
        if period < 1:
            raise ValueError("period must be >= 1")
        self.period = period
        self.alpha = 2.0 / (period + 1.0)
        self._seed = Rolling(period)
        self._ema: float | None = None

    def update(self, x: float) -> float | None:
        if self._ema is None:
            self._seed.update(x)
            if self._seed.full:
                self._ema = self._seed.mean
            return self._ema
        self._ema = self.alpha * x + (1.0 - self.alpha) * self._ema
        return self._ema

    @property
    def value(self) -> float | None:
        return self._ema


class WilderMA:
    """Wilder's smoothing (a.k.a. RMA/SMMA), seeded with the SMA of the first
    ``period`` inputs. Used by RSI, ATR and ADX. Recurrence:
    ``avg = (avg*(period-1) + x) / period``."""

    __slots__ = ("period", "_seed", "_val")

    def __init__(self, period: int) -> None:
        if period < 1:
            raise ValueError("period must be >= 1")
        self.period = period
        self._seed = Rolling(period)
        self._val: float | None = None

    def update(self, x: float) -> float | None:
        if self._val is None:
            self._seed.update(x)
            if self._seed.full:
                self._val = self._seed.mean
            return self._val
        self._val = (self._val * (self.period - 1) + x) / self.period
        return self._val

    @property
    def value(self) -> float | None:
        return self._val
