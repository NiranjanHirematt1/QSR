"""Contract specification — the source of truth for instrument economics.

For forex and futures, PnL is emphatically *not* ``(exit - entry) * qty``. It is
driven by the tick size, the cash value of a tick, and the contract multiplier.
Centralising this here means every downstream calculation (PnL, R-multiples,
slippage expressed in ticks, per-contract commission) derives from one object
instead of scattered magic numbers.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AssetClass(str, Enum):
    FX = "FX"
    FUTURE = "FUTURE"


@dataclass(frozen=True, slots=True)
class ContractSpec:
    """Immutable economic definition of a tradable instrument.

    Attributes:
        tick_size: Smallest price increment (e.g. ``0.00001`` for EURUSD,
            ``0.25`` for the ES future).
        tick_value: Cash value, in ``quote_currency``, of one tick per 1 unit
            of quantity (1 lot / 1 contract).
        contract_multiplier: Units of the underlying per 1 quantity. Used for
            futures (e.g. ES = 50). For FX this is the lot size in base-currency
            units (e.g. a standard lot = 100_000).
        quote_currency: Currency in which PnL is denominated.
        min_qty / qty_step: Quantity constraints for order validation.
        pip_size: (FX) price movement that constitutes one "pip", for reporting.
    """

    symbol: str
    asset_class: AssetClass
    tick_size: float
    tick_value: float
    contract_multiplier: float
    quote_currency: str
    min_qty: float = 1.0
    qty_step: float = 1.0
    pip_size: float | None = None

    def __post_init__(self) -> None:
        for name in ("tick_size", "tick_value", "contract_multiplier", "min_qty", "qty_step"):
            if getattr(self, name) <= 0:
                raise ValueError(f"ContractSpec.{name} must be positive")

    @property
    def point_value(self) -> float:
        """Cash value of a full 1.0 price move, per unit quantity."""
        return self.tick_value / self.tick_size

    def price_to_cash(self, price_delta: float, qty: float) -> float:
        """Convert a price move into cash PnL for a given quantity.

        This is the single canonical PnL primitive for the whole platform.
        """
        return price_delta * self.point_value * qty

    def ticks_to_price(self, ticks: float) -> float:
        """Convert a distance expressed in ticks into a price distance."""
        return ticks * self.tick_size

    def round_to_tick(self, price: float) -> float:
        """Snap a price to the nearest valid tick."""
        return round(price / self.tick_size) * self.tick_size

    def round_qty(self, qty: float) -> float:
        """Snap a quantity to the instrument's ``qty_step`` (floored)."""
        steps = int(qty / self.qty_step)
        return max(self.min_qty, steps * self.qty_step)
