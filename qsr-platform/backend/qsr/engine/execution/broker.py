"""Broker simulator — the single execution engine.

Deterministic, event-driven fills for a single net position per instrument.
Supports market/limit/stop entries, stop-loss/take-profit/trailing exits, and
partial closes, with commission, slippage and spread. Market orders fill at the
*next* bar's open (no same-bar-close cheat); resting orders fill when the bar's
range crosses their trigger; intrabar stop/target conflicts are resolved by the
configured :class:`IntrabarAssumption`.
"""
from __future__ import annotations

from dataclasses import dataclass

from ...domain.instruments.instrument import Instrument
from ...domain.market_data.candle import Candle
from ...domain.orders.intents import (
    CloseIntent,
    OrderIntent,
    OrderType,
    Side,
    StopLossIntent,
    TakeProfitIntent,
)
from ...domain.orders.trade import Trade
from ..portfolio.ledger import Ledger
from ..portfolio.position import Position
from ..portfolio.sizing import PositionSizer, StandardSizer
from .costs import CommissionModel, ExecutionCosts
from .fill_model import ExitReason, IntrabarAssumption, resolve_exit
from .orders import ProtectiveSpec, WorkingOrder


class BrokerSimulator:
    def __init__(
        self,
        instrument: Instrument,
        initial_capital: float,
        commission: CommissionModel,
        costs: ExecutionCosts,
        intrabar: IntrabarAssumption,
        ledger: Ledger,
        sizer: PositionSizer | None = None,
    ) -> None:
        self._inst = instrument
        self._spec = instrument.spec
        self._commission = commission
        self._costs = costs
        self._intrabar = intrabar
        self._ledger = ledger
        self._sizer = sizer or StandardSizer()

        self.position = Position(self._spec)
        self.realized_cash = initial_capital
        self._pending_market: list[WorkingOrder] = []
        self._resting: list[WorkingOrder] = []

    # ---- read views (for the strategy context) ------------------------------
    def equity(self, mark: float) -> float:
        return self.realized_cash + self.position.unrealized(mark)

    # ---- per-bar processing (called BEFORE the strategy acts) ---------------
    def process_bar(self, bar: Candle) -> None:
        # 1) market orders queued on the previous bar fill at this bar's open
        for order in self._pending_market:
            self._fill(order, self._costs.market(order.side, bar.open), bar)
        self._pending_market.clear()

        # 2) resting limit/stop orders triggered by this bar's range
        for order in list(self._resting):
            trigger = self._triggered_price(order, bar)
            if trigger is None:
                continue
            price = (self._costs.market(order.side, trigger)
                     if order.order_type in (OrderType.STOP, OrderType.STOP_LIMIT)
                     else self._costs.limit(order.side, trigger))
            self._fill(order, price, bar)
            self._resting.remove(order)

        # 3) stop-loss / take-profit on the open position (uses levels set on
        #    prior bars — never this bar's own trailing update)
        if self.position.is_open:
            hit = resolve_exit(self.position.is_long, bar,
                               self.position.stop, self.position.target, self._intrabar)
            if hit is not None:
                raw, reason = hit
                side = Side.SELL if self.position.is_long else Side.BUY
                price = (self._costs.market(side, raw) if reason is ExitReason.STOP
                         else self._costs.limit(side, raw))
                self._close(price, bar, reason.value)

        # 4) ratchet trailing stop from THIS bar's close for use on the NEXT bar
        if self.position.is_open and self.position.trailing_ticks is not None:
            self._update_trailing(bar)

    # ---- intent handling (called AFTER the strategy acts) -------------------
    def submit_intents(self, intents: list, ref_bar: Candle) -> None:
        entries = [i for i in intents if isinstance(i, OrderIntent)]
        closes = [i for i in intents if isinstance(i, CloseIntent)]
        stops = [i for i in intents if isinstance(i, StopLossIntent)]
        targets = [i for i in intents if isinstance(i, TakeProfitIntent)]

        for c in closes:
            self._queue_close(c)

        stop_spec = _to_spec(stops[-1]) if stops else None
        target_spec = _to_spec(targets[-1]) if targets else None

        if entries:
            self._queue_entry(entries[-1], ref_bar, stop_spec, target_spec)
        elif self.position.is_open:
            # adjust protective levels on the live position
            if stop_spec is not None:
                self.position.stop = stop_spec.resolve(
                    self.position.avg_price, self.position.is_long, True, self._spec.tick_size)
                if stop_spec.trailing:
                    self.position.trailing_ticks = stop_spec.offset_price(self._spec.tick_size)
            if target_spec is not None:
                self.position.target = target_spec.resolve(
                    self.position.avg_price, self.position.is_long, False, self._spec.tick_size)

    def close_all(self, bar: Candle, reason: str = "end_of_data") -> None:
        if self.position.is_open:
            side = Side.SELL if self.position.is_long else Side.BUY
            self._close(self._costs.market(side, bar.close), bar, reason)

    # ---- internals ----------------------------------------------------------
    def _queue_entry(self, intent: OrderIntent, ref_bar: Candle,
                     stop_spec: ProtectiveSpec | None, target_spec: ProtectiveSpec | None) -> None:
        stop_distance = stop_spec.offset_price(self._spec.tick_size) if stop_spec else None
        if stop_distance is None and stop_spec and stop_spec.price is not None:
            stop_distance = abs(ref_bar.close - stop_spec.price)
        qty = self._sizer.resolve(intent.size, price=ref_bar.close,
                                  equity=self.equity(ref_bar.close), contract=self._spec,
                                  stop_distance=stop_distance) if intent.size else self._spec.min_qty
        order = WorkingOrder(
            side=intent.side, order_type=intent.order_type, qty=qty,
            limit_price=intent.limit_price, stop_price=intent.stop_price,
            tag=intent.tag, reason=intent.reason,
            stop_spec=stop_spec, target_spec=target_spec,
            tags=(intent.tag,) if intent.tag else (),
        )
        if order.order_type is OrderType.MARKET:
            self._pending_market.append(order)
        else:
            self._resting.append(order)

    def _queue_close(self, intent: CloseIntent) -> None:
        if not self.position.is_open:
            return
        qty = intent.qty if intent.qty is not None else abs(self.position.qty)
        side = Side.SELL if self.position.is_long else Side.BUY
        self._pending_market.append(
            WorkingOrder(side=side, order_type=OrderType.MARKET, qty=qty,
                         reason=intent.reason or "signal", is_exit=True))

    def _triggered_price(self, order: WorkingOrder, bar: Candle) -> float | None:
        if order.order_type is OrderType.LIMIT:
            lp = order.limit_price
            if order.side is Side.BUY and bar.low <= lp:      # buy limit below price
                return min(bar.open, lp)
            if order.side is Side.SELL and bar.high >= lp:
                return max(bar.open, lp)
        elif order.order_type in (OrderType.STOP, OrderType.STOP_LIMIT):
            sp = order.stop_price
            if order.side is Side.BUY and bar.high >= sp:     # buy stop above price
                return max(bar.open, sp)
            if order.side is Side.SELL and bar.low <= sp:
                return min(bar.open, sp)
        return None

    def _fill(self, order: WorkingOrder, price: float, bar: Candle) -> None:
        p = self.position
        prev_qty = p.qty
        prev_avg = p.avg_price
        prev_time = p.entry_time
        prev_reason = p.entry_reason
        prev_stop0 = p.initial_stop
        prev_tags = p.tags
        prev_entry_comm = p.entry_commission

        signed = order.qty if order.side is Side.BUY else -order.qty
        opposing = prev_qty != 0 and (prev_qty > 0) != (signed > 0)
        closed = min(order.qty, abs(prev_qty)) if opposing else 0.0

        # Split this fill's commission across its closing and opening portions.
        comm_total = self._commission.charge(order.qty)
        exit_comm = comm_total * (closed / order.qty) if order.qty else 0.0
        open_comm = comm_total - exit_comm

        realized = p.apply_fill(order.side, price, order.qty)
        self.realized_cash += realized - comm_total

        if closed > 0:  # a round-trip (or part of one) closed: attribute BOTH sides
            entry_comm_portion = prev_entry_comm * (closed / abs(prev_qty))
            self._record_trade(prev_avg, price, closed, prev_qty > 0, prev_time, prev_reason,
                               prev_stop0, order.reason or "signal", bar,
                               exit_comm + entry_comm_portion, prev_tags)

        # Carry the correct entry-side commission on whatever position remains.
        if not p.is_open:
            p.entry_commission = 0.0
        elif opposing or prev_qty == 0:      # reversed into, or opened fresh
            p.entry_commission = open_comm
        else:                                # added in the same direction
            p.entry_commission = prev_entry_comm + open_comm

        opened = (prev_qty == 0 and p.is_open) or (opposing and p.is_open)
        if opened and not order.is_exit:
            keep_comm = p.entry_commission
            self._set_entry(order, price, bar)
            p.entry_commission = keep_comm

    def _set_entry(self, order: WorkingOrder, price: float, bar: Candle) -> None:
        p = self.position
        p.entry_time = bar.open_time
        p.entry_reason = order.reason
        p.tags = order.tags
        p.stop = p.initial_stop = p.target = None
        p.trailing_ticks = None
        if order.stop_spec is not None:
            p.stop = p.initial_stop = order.stop_spec.resolve(price, p.is_long, True, self._spec.tick_size)
            if order.stop_spec.trailing:
                p.trailing_ticks = order.stop_spec.offset_price(self._spec.tick_size)
        if order.target_spec is not None:
            p.target = order.target_spec.resolve(price, p.is_long, False, self._spec.tick_size)

    def _close(self, price: float, bar: Candle, reason: str) -> None:
        side = Side.SELL if self.position.is_long else Side.BUY
        qty = abs(self.position.qty)
        self._fill(WorkingOrder(side=side, order_type=OrderType.MARKET, qty=qty,
                                reason=reason, is_exit=True), price, bar)

    def _update_trailing(self, bar: Candle) -> None:
        d = self.position.trailing_ticks
        if self.position.is_long:
            candidate = bar.close - d
            self.position.stop = candidate if self.position.stop is None else max(self.position.stop, candidate)
        else:
            candidate = bar.close + d
            self.position.stop = candidate if self.position.stop is None else min(self.position.stop, candidate)

    def _record_trade(self, entry_price, exit_price, qty, was_long, entry_time, entry_reason,
                      initial_stop, exit_reason, bar, commission, tags) -> None:
        direction = 1 if was_long else -1
        pnl = self._spec.price_to_cash(exit_price - entry_price, qty * direction) - commission
        r_multiple = None
        if initial_stop is not None:
            risk_per_unit = abs(entry_price - initial_stop) * self._spec.point_value
            risk_cash = risk_per_unit * qty
            if risk_cash > 0:
                r_multiple = pnl / risk_cash
        self._ledger.record_trade(Trade(
            instrument=self._inst.symbol,
            side=Side.BUY if was_long else Side.SELL,
            qty=qty,
            entry_time=entry_time or bar.open_time,
            exit_time=bar.open_time,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl=pnl,
            r_multiple=r_multiple,
            commission=commission,
            entry_reason=entry_reason,
            exit_reason=exit_reason,
            tags=tags,
        ))


def _to_spec(intent) -> ProtectiveSpec:
    return ProtectiveSpec(price=intent.price, ticks=intent.ticks, distance=intent.distance,
                          trailing=getattr(intent, "trailing", False))
