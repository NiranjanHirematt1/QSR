"""Structured output value objects for multi-line indicators.

Single-line indicators (SMA, EMA, RSI, ATR, VWMA) output a plain ``float``.
Multi-line indicators output one of these immutable records so consumers get
named fields instead of positional tuples.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MACDValue:
    macd: float
    signal: float
    histogram: float


@dataclass(frozen=True, slots=True)
class BandsValue:
    upper: float
    middle: float
    lower: float


@dataclass(frozen=True, slots=True)
class ADXValue:
    adx: float
    plus_di: float
    minus_di: float


@dataclass(frozen=True, slots=True)
class SuperTrendValue:
    value: float
    direction: int  # +1 = uptrend (support below price), -1 = downtrend
