"""London Opening Range Breakout (ORB).

Classic session breakout: watch the first ``range_minutes`` after the London
session opens, record the high/low of that window as "the range", then take
one trade in whichever direction price *closes* outside it — long above the
range high, short below the range low. The stop sits on the opposite side of
the range; the target is a configurable multiple of the range's width. Flat
by a configurable session cutoff, at most one trade per calendar day.

Timezone note
--------------
All timestamps the engine hands a strategy (``ctx.now``) are UTC — the
importer converts everything to UTC on ingest, regardless of the source file's
original timezone (see ``ColumnMapping.source_tz``). So ``session_start_hour``
below is a UTC hour, and it only lines up with the *real* London open if your
data was imported with the correct ``source_tz``:

  * London opens 08:00 local. In UTC that's 07:00 during BST (late Mar-late
    Oct) and 08:00 during GMT (late Oct-late Mar). This strategy does not
    handle the DST switch itself — pick the UTC hour that matches the period
    you're testing, or split your backtest date range across the change.
  * If you're not sure your import's ``source_tz`` was set correctly, check a
    few candles around a time you know (e.g. the US cash open, 13:30 UTC in
    summer / 14:30 UTC in winter, or 09:30 ET) against the chart.

This file only needs to exist under ``qsr/strategies/library/`` — strategies
are auto-discovered by filename, so no registration step is required. It'll
show up as ``london_orb`` in the strategy list / API / UI immediately.
"""
from __future__ import annotations

from datetime import date

from qsr.domain.market_data.timeframe import Timeframe
from qsr.domain.orders.intents import SizeKind, SizeSpec
from qsr.domain.strategy.adapter import StrategyRequirements
from qsr.strategies.base import ParamSpec, RegisteredStrategy


class LondonOrb(RegisteredStrategy):
    name = "london_orb"
    params_schema = (
        ParamSpec("session_start_hour", 7,
                   description="UTC hour the opening range starts (London open: "
                               "~07:00 UTC in BST, ~08:00 UTC in GMT)"),
        ParamSpec("session_start_minute", 0, description="UTC minute the opening range starts"),
        ParamSpec("range_minutes", 30, description="Length of the opening range, in minutes"),
        ParamSpec("session_end_hour", 11,
                   description="UTC hour after which no new entries are taken and any "
                               "open trade is flattened (avoids holding into thin/"
                               "unrelated later sessions)"),
        ParamSpec("risk_pct", 1.0, description="Risk per trade, % of equity"),
        ParamSpec("reward_multiple", 2.0,
                   description="Take-profit distance as a multiple of the opening-range width"),
        ParamSpec("stop_buffer", 0.0,
                   description="Extra distance added beyond the range for the stop, in the "
                               "instrument's own price units (e.g. 0.0002 for ~2 pips on "
                               "EURUSD). Default 0 = stop exactly at the range edge."),
        ParamSpec("timeframe_seconds", 60,
                   description="Bar timeframe in seconds; must match your imported data's resolution"),
    )

    def __init__(self, session_start_hour: int = 7, session_start_minute: int = 0,
                 range_minutes: int = 30, session_end_hour: int = 11,
                 risk_pct: float = 1.0, reward_multiple: float = 2.0,
                 stop_buffer: float = 0.0, timeframe_seconds: int = 60) -> None:
        super().__init__()
        self.session_start_hour = int(session_start_hour)
        self.session_start_minute = int(session_start_minute)
        self.range_minutes = int(range_minutes)
        self.session_end_hour = int(session_end_hour)
        self.risk_pct = float(risk_pct)
        self.reward_multiple = float(reward_multiple)
        self.stop_buffer = float(stop_buffer)
        self.tf = Timeframe(int(timeframe_seconds))

        # Per-day state, reset whenever the calendar date (UTC) changes.
        self._day: date | None = None
        self._range_high: float | None = None
        self._range_low: float | None = None
        self._traded_today: bool = False

    def initialize(self) -> StrategyRequirements:
        return StrategyRequirements(timeframes=(self.tf,))

    # ---- internals ----------------------------------------------------------
    def _minutes_since_session_start(self, now) -> int:
        start_today = now.replace(hour=self.session_start_hour,
                                  minute=self.session_start_minute,
                                  second=0, microsecond=0)
        return int((now - start_today).total_seconds() // 60)

    def _reset_for_new_day(self, today: date) -> None:
        self._day = today
        self._range_high = None
        self._range_low = None
        self._traded_today = False

    # ---- main loop ------------------------------------------------------------
    def on_bar(self) -> None:
        now = self.ctx.now
        bar = self.ctx.bar(self.tf)
        if bar is None:
            return

        today = now.date()
        if today != self._day:
            self._reset_for_new_day(today)

        elapsed = self._minutes_since_session_start(now)

        # Inside the opening-range window: extend the range, do nothing else yet.
        if 0 <= elapsed < self.range_minutes:
            self._range_high = bar.high if self._range_high is None else max(self._range_high, bar.high)
            self._range_low = bar.low if self._range_low is None else min(self._range_low, bar.low)
            return

        # Before the session has opened, or no range ever formed today: nothing to do.
        if self._range_high is None or self._range_low is None:
            return

        # Past the session cutoff: flatten (if needed) and stop looking for entries.
        if now.hour >= self.session_end_hour:
            if self.ctx.position_qty != 0:
                self.close(reason="session_end")
            return

        # Already took today's one trade, or currently in a position: wait.
        if self._traded_today or self.ctx.position_qty != 0:
            return

        range_width = self._range_high - self._range_low
        if range_width <= 0:
            return  # degenerate range (e.g. a single flat print) -- skip today

        target_distance = range_width * self.reward_multiple

        # Breakout is confirmed on a *closing* price beyond the range, not just
        # an intrabar touch/wick -- filters out some fakeouts. (The engine has
        # no "cancel a resting order" primitive to expire an unfilled breakout
        # stop order at session end, which is why this uses a close-confirmed
        # market entry rather than resting buy-stop/sell-stop orders left at
        # the range edges.)
        if bar.close > self._range_high:
            self.buy(SizeSpec(SizeKind.RISK_PERCENT, self.risk_pct), reason="london_orb_break_up")
            self.set_stoploss(price=self._range_low - self.stop_buffer, tag="orb_stop")
            self.set_takeprofit(distance=target_distance, tag="orb_target")
            self._traded_today = True
        elif bar.close < self._range_low:
            self.sell(SizeSpec(SizeKind.RISK_PERCENT, self.risk_pct), reason="london_orb_break_down")
            self.set_stoploss(price=self._range_high + self.stop_buffer, tag="orb_stop")
            self.set_takeprofit(distance=target_distance, tag="orb_target")
            self._traded_today = True