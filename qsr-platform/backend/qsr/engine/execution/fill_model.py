"""Intrabar fill sequencing — an explicit, recorded assumption.

Within a single bar we know only O/H/L/C, not the path price took. When a
position's stop-loss and take-profit both lie inside one bar's range, which one
fills first materially changes results. Rather than hide this (as most testers
do), we make it a first-class, configurable, and reproducible assumption:

* ``PESSIMISTIC`` (default) — assume the adverse level (stop) is reached first.
* ``OPTIMISTIC``          — assume the favourable level (target) is reached first.
* ``OHLC_PATH``           — infer order from the bar's shape: an up bar is
                            assumed to travel O->H->L->C, a down bar O->L->H->C.

Gaps take precedence: if the bar's open is already beyond a level, that level
fills at the open (the first available price).
"""
from __future__ import annotations

from enum import Enum

from ...domain.market_data.candle import Candle


class IntrabarAssumption(str, Enum):
    PESSIMISTIC = "PESSIMISTIC"
    OPTIMISTIC = "OPTIMISTIC"
    OHLC_PATH = "OHLC_PATH"


class ExitReason(str, Enum):
    STOP = "stop"
    TARGET = "target"


def resolve_exit(
    is_long: bool,
    bar: Candle,
    stop: float | None,
    target: float | None,
    assumption: IntrabarAssumption,
) -> tuple[float, ExitReason] | None:
    """Return the raw exit ``(price, reason)`` for an open position on this bar,
    or ``None`` if neither level is touched. Transaction costs are applied by the
    caller (slippage hits stops, not targets)."""
    if is_long:
        stop_hit = stop is not None and bar.low <= stop
        target_hit = target is not None and bar.high >= target
        stop_fill = min(bar.open, stop) if stop_hit else None      # gap-down fills worse
        target_fill = max(bar.open, target) if target_hit else None  # gap-up fills better
        open_through_stop = stop_hit and bar.open <= stop  # type: ignore[operator]
        open_through_target = target_hit and bar.open >= target  # type: ignore[operator]
    else:
        stop_hit = stop is not None and bar.high >= stop
        target_hit = target is not None and bar.low <= target
        stop_fill = max(bar.open, stop) if stop_hit else None
        target_fill = min(bar.open, target) if target_hit else None
        open_through_stop = stop_hit and bar.open >= stop  # type: ignore[operator]
        open_through_target = target_hit and bar.open <= target  # type: ignore[operator]

    if not stop_hit and not target_hit:
        return None
    if stop_hit and not target_hit:
        return (stop_fill, ExitReason.STOP)  # type: ignore[return-value]
    if target_hit and not stop_hit:
        return (target_fill, ExitReason.TARGET)  # type: ignore[return-value]

    # Both hit in the same bar. Open-gap precedence first.
    if open_through_stop and not open_through_target:
        return (stop_fill, ExitReason.STOP)  # type: ignore[return-value]
    if open_through_target and not open_through_stop:
        return (target_fill, ExitReason.TARGET)  # type: ignore[return-value]

    stop_first = _stop_first(is_long, bar, assumption)
    if stop_first:
        return (stop_fill, ExitReason.STOP)  # type: ignore[return-value]
    return (target_fill, ExitReason.TARGET)  # type: ignore[return-value]


def _stop_first(is_long: bool, bar: Candle, assumption: IntrabarAssumption) -> bool:
    if assumption is IntrabarAssumption.PESSIMISTIC:
        return True
    if assumption is IntrabarAssumption.OPTIMISTIC:
        return False
    # OHLC_PATH: up bar travels O->H->L->C, down bar O->L->H->C.
    up_bar = bar.close >= bar.open
    if is_long:
        # stop is the low-side event; reached first only on a down bar.
        return not up_bar
    # short: stop is the high-side event; reached first on an up bar.
    return up_bar
