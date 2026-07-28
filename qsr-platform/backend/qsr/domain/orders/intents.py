"""Order Intent IR — the language-agnostic boundary of the strategy layer.

This is the single most important seam in the platform. A strategy — written in
Python today, or Pine Script / a Visual Builder / an AI model tomorrow — never
mutates positions or talks to the engine directly. It emits a stream of
*declarative intents*: "I would like to buy 2 contracts at market", "attach a
stop 15 ticks away". The engine consumes intents and decides fills.

Because intents are plain, serialisable value objects (not Python callables),
an out-of-process runtime in any language can produce them as JSON and hand them
to the engine over stdio/socket. That is what makes the engine *language
agnostic*: adding a new strategy language means writing a new adapter that emits
these same intents. The engine code does not change.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class TimeInForce(str, Enum):
    GTC = "GTC"
    DAY = "DAY"
    GTD = "GTD"


@dataclass(frozen=True, slots=True)
class OrderIntent:
    """A declarative request to open or add to a position.

    ``size`` is intentionally *not* resolved to a contract quantity here: it may
    be a raw quantity or a sizing directive (risk %, fixed cash) resolved later
    by a :class:`PositionSizer`. Keeping it symbolic keeps the IR portable.
    """

    side: Side
    order_type: OrderType = OrderType.MARKET
    size: "SizeSpec | None" = None
    limit_price: float | None = None
    stop_price: float | None = None
    tif: TimeInForce = TimeInForce.GTC
    tag: str | None = None
    reason: str | None = None  # captured for the Trade Explorer ("why")


@dataclass(frozen=True, slots=True)
class CloseIntent:
    """Request to flatten the position, or a portion of it.

    ``qty`` is the number of units to close; ``None`` means close the whole
    position (supports partial exits without changing the engine contract)."""

    tag: str | None = None
    qty: float | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class StopLossIntent:
    """Attach/replace a protective stop. Exactly one of ``price``/``ticks``/
    ``distance`` is provided; resolution to a concrete price happens in the
    engine using the instrument's :class:`ContractSpec`.

    When ``trailing`` is set, the stop follows price at the given
    ticks/distance offset (never moving against the position)."""

    price: float | None = None
    ticks: float | None = None
    distance: float | None = None
    trailing: bool = False
    tag: str | None = None


@dataclass(frozen=True, slots=True)
class TakeProfitIntent:
    price: float | None = None
    ticks: float | None = None
    distance: float | None = None
    tag: str | None = None


# --- position sizing directives (symbolic; resolved by the engine) -----------
class SizeKind(str, Enum):
    FIXED_QTY = "FIXED_QTY"
    FIXED_CASH = "FIXED_CASH"
    RISK_PERCENT = "RISK_PERCENT"


@dataclass(frozen=True, slots=True)
class SizeSpec:
    """Portable sizing directive. ``RISK_PERCENT`` is resolved against the
    attached stop distance and the contract's point value at execution time."""

    kind: SizeKind
    value: float
