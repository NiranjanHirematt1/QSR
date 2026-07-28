"""Backtest configuration — all knobs live here; nothing is hardcoded in logic."""
from __future__ import annotations

from dataclasses import dataclass

from .execution.fill_model import IntrabarAssumption


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    """Immutable run configuration.

    Attributes:
        initial_capital: Starting cash in the instrument's quote currency.
        commission_per_unit: Cash commission charged per unit (contract/lot) per fill.
        slippage_ticks: Adverse slippage, in ticks, applied to market & stop fills.
        spread_ticks: Full bid/ask spread in ticks; half is applied to each side.
        intrabar: Assumption for resolving same-bar stop/target conflicts.
        close_at_end: If True, any open position is closed at the last bar's close.
    """

    initial_capital: float = 100_000.0
    commission_per_unit: float = 0.0
    slippage_ticks: float = 0.0
    spread_ticks: float = 0.0
    intrabar: IntrabarAssumption = IntrabarAssumption.PESSIMISTIC
    close_at_end: bool = True
