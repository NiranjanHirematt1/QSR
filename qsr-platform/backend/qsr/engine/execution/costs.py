"""Transaction cost models: commission, slippage, spread — forex/futures aware.

Slippage and spread are expressed in *ticks* (not percent), which is the correct
unit for futures/FX, and converted to price via the instrument's tick size.
"""
from __future__ import annotations

from dataclasses import dataclass

from ...domain.instruments.contract_spec import ContractSpec
from ...domain.orders.intents import Side


@dataclass(frozen=True, slots=True)
class CommissionModel:
    """Flat cash commission per unit (contract/lot) per fill."""

    per_unit: float = 0.0

    def charge(self, qty: float) -> float:
        return self.per_unit * abs(qty)


@dataclass(frozen=True, slots=True)
class ExecutionCosts:
    """Applies slippage and half-spread to a raw fill price, adverse to the
    order side (buys fill higher, sells fill lower)."""

    spec: ContractSpec
    slippage_ticks: float = 0.0
    spread_ticks: float = 0.0

    def _adverse(self, side: Side, ticks: float) -> float:
        offset = self.spec.ticks_to_price(ticks)
        return offset if side is Side.BUY else -offset

    def market(self, side: Side, price: float) -> float:
        """Market/stop fills incur both slippage and half the spread."""
        return price + self._adverse(side, self.slippage_ticks + self.spread_ticks / 2.0)

    def limit(self, side: Side, price: float) -> float:
        """Resting limit fills cross only the half-spread (no slippage)."""
        return price + self._adverse(side, self.spread_ticks / 2.0)
