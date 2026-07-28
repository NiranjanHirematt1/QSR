"""Position sizing strategies (Strategy pattern). New rule = one class."""
from __future__ import annotations

from typing import Protocol

from ...domain.instruments.contract_spec import ContractSpec
from ...domain.orders.intents import SizeKind, SizeSpec


class PositionSizer(Protocol):
    def resolve(self, spec: SizeSpec, *, price: float, equity: float,
                contract: ContractSpec, stop_distance: float | None) -> float: ...


class StandardSizer:
    """Resolves all built-in :class:`SizeKind` variants to a contract quantity,
    snapped to the instrument's ``qty_step``."""

    def resolve(self, spec: SizeSpec, *, price: float, equity: float,
                contract: ContractSpec, stop_distance: float | None) -> float:
        if spec.kind is SizeKind.FIXED_QTY:
            qty = spec.value
        elif spec.kind is SizeKind.FIXED_CASH:
            notional_per_unit = price * contract.point_value
            qty = spec.value / notional_per_unit if notional_per_unit else 0.0
        elif spec.kind is SizeKind.RISK_PERCENT:
            if not stop_distance or stop_distance <= 0:
                raise ValueError("RISK_PERCENT sizing requires a stop distance > 0")
            risk_cash = equity * (spec.value / 100.0)
            qty = risk_cash / (stop_distance * contract.point_value)
        else:  # pragma: no cover - exhaustive
            raise ValueError(f"Unknown size kind {spec.kind}")
        return contract.round_qty(qty)
