"""Working orders — intents resolved into executable orders held by the broker."""
from __future__ import annotations

from dataclasses import dataclass, field

from ...domain.orders.intents import OrderType, Side


@dataclass(frozen=True, slots=True)
class ProtectiveSpec:
    """Deferred stop/target definition, resolved to a price when the entry fills
    (so ticks/distance are measured from the actual fill price)."""

    price: float | None = None
    ticks: float | None = None
    distance: float | None = None
    trailing: bool = False

    def resolve(self, fill_price: float, side_is_long: bool, is_stop: bool, tick_size: float) -> float:
        if self.price is not None:
            return self.price
        offset = (self.ticks * tick_size) if self.ticks is not None else (self.distance or 0.0)
        # Stops sit adverse to the position; targets sit favourable.
        below = is_stop if side_is_long else (not is_stop)
        return fill_price - offset if below else fill_price + offset

    def offset_price(self, tick_size: float) -> float | None:
        if self.ticks is not None:
            return self.ticks * tick_size
        return self.distance


@dataclass(slots=True)
class WorkingOrder:
    side: Side
    order_type: OrderType
    qty: float                      # resolved, unsigned
    limit_price: float | None = None
    stop_price: float | None = None
    tag: str | None = None
    reason: str | None = None
    is_exit: bool = False
    stop_spec: ProtectiveSpec | None = None
    target_spec: ProtectiveSpec | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
