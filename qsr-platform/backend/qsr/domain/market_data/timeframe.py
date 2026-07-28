"""Timeframe value object.

A :class:`Timeframe` is the atomic unit of time granularity in the platform.
Everything downstream (resampling, the multi-timeframe clock, indicators) speaks
in terms of these objects rather than raw strings or integers, so there is one
canonical definition of "what an H1 bar is" for the entire system.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True, slots=True, order=True)
class Timeframe:
    """An immutable timeframe defined purely by its length in seconds.

    Ordering is by ``seconds`` so timeframes can be sorted (finest -> coarsest),
    which the multi-timeframe clock relies on.
    """

    seconds: int

    def __post_init__(self) -> None:
        if self.seconds <= 0:
            raise ValueError(f"Timeframe seconds must be positive, got {self.seconds}")

    # ---- constructors -------------------------------------------------------
    @classmethod
    def from_label(cls, label: str) -> "Timeframe":
        """Parse a human label such as ``"M5"``, ``"H1"``, ``"D1"``.

        Supported units: ``S`` seconds, ``M`` minutes, ``H`` hours, ``D`` days,
        ``W`` weeks. The label is case-insensitive.
        """
        s = label.strip().upper()
        if len(s) < 2:
            raise ValueError(f"Unrecognised timeframe label: {label!r}")
        unit, num = s[0], s[1:]
        try:
            n = int(num)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Unrecognised timeframe label: {label!r}") from exc
        unit_seconds = {"S": 1, "M": 60, "H": 3600, "D": 86400, "W": 604800}
        if unit not in unit_seconds:
            raise ValueError(f"Unknown timeframe unit {unit!r} in {label!r}")
        return cls(n * unit_seconds[unit])

    # ---- derived views ------------------------------------------------------
    @property
    def delta(self) -> timedelta:
        return timedelta(seconds=self.seconds)

    @property
    def label(self) -> str:
        """Canonical short label, e.g. ``"M5"``. Chooses the largest exact unit."""
        for unit, size in (("W", 604800), ("D", 86400), ("H", 3600), ("M", 60), ("S", 1)):
            if self.seconds % size == 0:
                return f"{unit}{self.seconds // size}"
        return f"S{self.seconds}"  # pragma: no cover

    def is_multiple_of(self, base: "Timeframe") -> bool:
        """True if this timeframe cleanly aggregates ``base`` bars.

        A higher timeframe can only be *derived* from a base timeframe when it is
        an exact integer multiple, otherwise resampling would be ambiguous.
        """
        return self.seconds % base.seconds == 0

    def floor(self, ts: datetime) -> datetime:
        """Return the open-time of the bar of this timeframe containing ``ts``.

        Anchored to the Unix epoch (UTC). ``ts`` must be timezone-aware UTC.
        """
        if ts.tzinfo is None:
            raise ValueError("floor() requires a timezone-aware UTC datetime")
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        elapsed = int((ts - epoch).total_seconds())
        floored = elapsed - (elapsed % self.seconds)
        return epoch + timedelta(seconds=floored)

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.label
