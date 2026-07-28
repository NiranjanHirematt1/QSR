"""Session calendars.

Forex and futures do not trade continuously: FX has a weekend gap, and futures
have daily maintenance breaks. The calendar answers whether a timestamp is
in-session, which lets the gap validator avoid flagging *expected* closures as
missing data, and lets daily resampling break on the correct boundary.

The interface is deliberately small and framework-free so alternative
implementations (holiday-aware exchange calendars, crypto 24/7) can be dropped
in without touching callers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Protocol, runtime_checkable


@runtime_checkable
class SessionCalendar(Protocol):
    """Port: decides when a market is open."""

    def is_open(self, ts: datetime) -> bool: ...

    def session_day_start(self, ts: datetime) -> datetime:
        """Open-time of the trading 'day' that ``ts`` belongs to.

        Used as the anchor for daily (and higher) resampling, since a futures
        session day rarely starts at 00:00 UTC.
        """
        ...


@dataclass(frozen=True, slots=True)
class ContinuousCalendar:
    """24/7 calendar — every timestamp is in-session (e.g. crypto, or a
    simplification for always-on research)."""

    def is_open(self, ts: datetime) -> bool:
        return True

    def session_day_start(self, ts: datetime) -> datetime:
        return ts.replace(hour=0, minute=0, second=0, microsecond=0)


@dataclass(frozen=True, slots=True)
class ForexWeekendCalendar:
    """Spot-FX style calendar: open from Sunday ``open_hour`` UTC to Friday
    ``close_hour`` UTC, closed over the weekend.

    Times are in UTC. This is intentionally simple (no bank holidays yet); a
    holiday-aware variant is a future adapter implementing the same Protocol.
    """

    open_weekday: int = 6      # Sunday
    open_hour: int = 22        # ~Sydney open
    close_weekday: int = 4     # Friday
    close_hour: int = 22       # ~NY close
    day_anchor: time = field(default=time(22, 0))  # daily bar boundary (UTC)

    def is_open(self, ts: datetime) -> bool:
        wd = ts.weekday()  # Mon=0 .. Sun=6
        if wd == 5:  # Saturday
            return False
        if wd == self.open_weekday:      # Sunday
            return ts.hour >= self.open_hour
        if wd == self.close_weekday:     # Friday
            return ts.hour < self.close_hour
        return True

    def session_day_start(self, ts: datetime) -> datetime:
        anchor = ts.replace(hour=self.day_anchor.hour, minute=self.day_anchor.minute,
                            second=0, microsecond=0)
        if ts < anchor:
            anchor -= timedelta(days=1)
        return anchor
