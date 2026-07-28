"""Annualization periodicity.

Risk ratios (Sharpe/Sortino/Calmar) need a periods-per-year factor. Rather than
a magic ``252``, it is derived from the strategy's base timeframe and an explicit
trading-calendar assumption (near-24h for FX/futures by default), and is fully
configurable.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Periodicity:
    trading_days_per_year: float = 252.0
    hours_per_day: float = 24.0  # FX/futures trade ~around the clock

    def periods_per_year(self, timeframe_seconds: int) -> float:
        seconds = self.trading_days_per_year * self.hours_per_day * 3600.0
        return seconds / timeframe_seconds
