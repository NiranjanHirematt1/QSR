"""Validator port + validation context."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import polars as pl

from ...domain.instruments.session_calendar import SessionCalendar
from ...domain.market_data.timeframe import Timeframe
from .report import Issue


@dataclass(frozen=True, slots=True)
class ValidationContext:
    """Everything a validator may need, injected (no globals)."""

    declared_timeframe: Timeframe
    calendar: SessionCalendar


@runtime_checkable
class Validator(Protocol):
    """A single, independent data-quality check. Adding a new check = one new
    class implementing this protocol + one registry entry."""

    def check(self, df: pl.DataFrame, ctx: ValidationContext) -> list[Issue]: ...
