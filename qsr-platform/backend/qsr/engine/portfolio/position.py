"""Position accounting with correct forex/futures economics.

A position uses **signed quantity** (long > 0, short < 0). PnL flows entirely
through :meth:`ContractSpec.price_to_cash`, so ``point_value`` / ``tick_value``
drive the numbers — never ``(exit - entry) * qty``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ...domain.instruments.contract_spec import ContractSpec
from ...domain.orders.intents import Side


@dataclass(slots=True)
class Position:
    spec: ContractSpec
    qty: float = 0.0                 # signed
    avg_price: float = 0.0
    entry_time: datetime | None = None
    entry_reason: str | None = None
    initial_stop: float | None = None
    stop: float | None = None
    target: float | None = None
    trailing_ticks: float | None = None
    entry_commission: float = 0.0    # accrued entry-side commission, for round-trip attribution
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_open(self) -> bool:
        return self.qty != 0.0

    @property
    def is_long(self) -> bool:
        return self.qty > 0.0

    @property
    def direction(self) -> int:
        return 1 if self.qty > 0 else (-1 if self.qty < 0 else 0)

    def unrealized(self, mark: float) -> float:
        if not self.is_open:
            return 0.0
        return self.spec.price_to_cash(mark - self.avg_price, self.qty)

    # ---- mutation (returns realized cash for the affected portion) ----------
    def apply_fill(self, side: Side, price: float, qty: float) -> float:
        """Apply a fill of ``qty`` (unsigned) on ``side``; return realized PnL.

        Handles opening, adding, reducing, closing and reversing. Realized PnL
        is produced only for the portion that offsets existing exposure.
        """
        signed = qty if side is Side.BUY else -qty
        realized = 0.0

        if self.qty == 0 or (self.qty > 0) == (signed > 0):
            # opening or adding in the same direction -> weighted average price
            new_qty = self.qty + signed
            self.avg_price = (
                (self.avg_price * abs(self.qty) + price * qty) / abs(new_qty)
                if new_qty != 0 else 0.0
            )
            self.qty = new_qty
            return 0.0

        # opposite direction -> reduce/close/reverse
        closing = min(abs(signed), abs(self.qty))
        closed_signed = closing * self.direction  # same sign as existing position
        realized = self.spec.price_to_cash(price - self.avg_price, closed_signed)
        self.qty += signed

        if self.qty == 0:
            self._reset_after_close()
        elif (self.qty > 0) != ((self.qty - signed) > 0):
            # reversed through zero: remainder opens a new position at fill price
            self.avg_price = price
            self._reset_after_close(keep_open=True)
        return realized

    def _reset_after_close(self, keep_open: bool = False) -> None:
        self.initial_stop = self.stop = self.target = None
        self.trailing_ticks = None
        self.entry_commission = 0.0
        if not keep_open:
            self.avg_price = 0.0
            self.entry_time = None
            self.entry_reason = None
            self.tags = ()
